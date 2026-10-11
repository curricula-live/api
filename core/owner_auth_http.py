"""BFF-only POST contracts for passwordless owner authentication.

All three handlers require a secret known exclusively to the Django API and
the admin server. Browsers NEVER call these directly, and Django NEVER sets
the admin-domain cookie. No magic link is consumed via GET.

Activation requires both OWNER_AUTH_ENABLED and OWNER_AUTH_HTTP_ENABLED,
a strong BFF secret, configured sender, and an allowlisted link destination.
The defaults intentionally fail closed.
"""
from __future__ import annotations

import hmac
import json
from urllib.parse import quote, urlsplit

from django.conf import settings
from django.core.mail import send_mail
from django.db import DatabaseError
from django.http import Http404, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from core.owner_rate_limit import consume_owner_request_quota

from core.owner_passwordless import (
    issue_challenge,
    normalized_email,
    redeem_challenge,
    revoke_session,
)

MAX_JSON_BYTES = 2048
NEUTRAL = {"message": "If an eligible account exists, a sign-in email will be sent."}


def _link_destination() -> str | None:
    configured = getattr(settings, "OWNER_LOGIN_LINK_BASE", "")
    if not isinstance(configured, str):
        return None
    try:
        url = urlsplit(configured)
        if url.username or url.password or url.query or url.fragment:
            return None
        production = (
            url.scheme == "https"
            and url.netloc == "admin.curricula.live"
            and url.path == "/login/verify"
        )
        local = (
            not settings.IS_PRODUCTION
            and url.scheme == "http"
            and url.hostname in ("localhost", "127.0.0.1")
            and url.port == 3000
            and url.path == "/login/verify"
        )
    except ValueError:
        # Invalid TCP port, malformed URL or URL-split credentials fail closed.
        return None
    if not (production or local):
        return None
    return configured


def _configured() -> bool:
    secret = getattr(settings, "OWNER_BFF_SHARED_SECRET", "")
    sender = getattr(settings, "OWNER_LOGIN_SENDER", "")
    return (
        # Production requires a shared rate limiter and asynchronous email
        # delivery to avoid enumeration through SMTP response timing.
        not settings.IS_PRODUCTION
        and getattr(settings, "OWNER_AUTH_ENABLED", False)
        and getattr(settings, "OWNER_AUTH_HTTP_ENABLED", False)
        and isinstance(secret, str)
        and len(secret) >= 32
        and isinstance(sender, str)
        and bool(sender.strip())
        and isinstance(getattr(settings, "OWNER_RATE_LIMIT_KEY", ""), str)
        and len(getattr(settings, "OWNER_RATE_LIMIT_KEY", "").encode("utf-8")) >= 32
        and (
            not getattr(settings, "OWNER_ASYNC_MAIL_ENABLED", False)
            or (
                isinstance(getattr(settings, "OWNER_EMAIL_TOKEN_KEY", ""), str)
                and len(getattr(settings, "OWNER_EMAIL_TOKEN_KEY", "").encode("utf-8")) >= 32
            )
        )
        and _link_destination() is not None
    )


def _security_headers(response: HttpResponse) -> HttpResponse:
    response["Cache-Control"] = "private, no-store"
    response["Referrer-Policy"] = "no-referrer"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _json(data: dict, status: int = 200) -> HttpResponse:
    return _security_headers(JsonResponse(data, status=status))


def _guard(request) -> HttpResponse | None:
    if not _configured():
        raise Http404("Unavailable")
    # These routes are deliberately server-to-server; browser requests and
    # cross-site form posts must use the same-origin admin BFF instead.
    if request.headers.get("Origin") or request.headers.get("Sec-Fetch-Site"):
        return _json({"error": "forbidden"}, status=403)
    provided = request.headers.get("X-Admin-BFF-Secret", "")
    expected = settings.OWNER_BFF_SHARED_SECRET
    if not isinstance(provided, str) or not hmac.compare_digest(provided, expected):
        return _json({"error": "forbidden"}, status=403)
    return None


def _body(request) -> dict | None:
    if request.content_type != "application/json" or len(request.body) > MAX_JSON_BYTES:
        return None
    try:
        value = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


@csrf_exempt
@require_POST
def request_owner_link(request) -> HttpResponse:
    denied = _guard(request)
    if denied is not None:
        return denied
    body = _body(request)
    if body is None:
        return _json({"error": "invalid request"}, status=400)

    # Valid and unknown email identities must receive indistinguishable
    # success responses. No owner lookup result is serialized to the caller.
    email = body.get("email")
    normalized = normalized_email(email)
    if normalized:
        try:
            quota_ok = consume_owner_request_quota(normalized)
            queued = getattr(settings, "OWNER_ASYNC_MAIL_ENABLED", False) is True
            if queued:
                # Persist the challenge and outbox ticket in one transaction.
                # No network/email operation runs on this HTTP request.
                issued = issue_challenge(normalized, queue_delivery=True) if quota_ok else None
            else:
                issued = issue_challenge(normalized) if quota_ok else None
            if issued is not None and not queued:
                link = f"{_link_destination()}#challenge={quote(issued.token, safe='')}"
                # Do not log the link or raw challenge; send only after commit.
                send_mail(
                    "Sign in to curricula.live administration",
                    "Open the following link and explicitly confirm sign-in. "
                    "This link expires in 10 minutes and can be used only once.\n\n"
                    f"{link}\n",
                    settings.OWNER_LOGIN_SENDER,
                    [normalized],
                    fail_silently=False,
                )
        except Exception:
            # A uniform response also avoids leaking owner membership and
            # provider failures. Operational alerting is a separate requirement.
            pass
    return _json(NEUTRAL, status=202)


@csrf_exempt
@require_POST
def redeem_owner_link(request) -> HttpResponse:
    denied = _guard(request)
    if denied is not None:
        return denied
    body = _body(request)
    if body is None:
        return _json({"error": "invalid request"}, status=400)
    token = body.get("challenge")
    if not isinstance(token, str):
        return _json({"error": "invalid challenge"}, status=401)
    try:
        session = redeem_challenge(token)
    except DatabaseError:
        return _json({"error": "authentication unavailable"}, status=503)
    if session is None:
        return _json({"error": "invalid challenge"}, status=401)
    # Only the trusted BFF receives this credential in a no-store POST body.
    return _json(
        {"session_token": session.token, "expires_at": session.expires_at.isoformat()},
        status=200,
    )


@csrf_exempt
@require_POST
def logout_owner_session(request) -> HttpResponse:
    denied = _guard(request)
    if denied is not None:
        return denied
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return _json({"error": "unauthorized"}, status=401)
    token = authorization[len("Bearer "):]
    try:
        revoke_session(token)
    except DatabaseError:
        return _json({"error": "authentication unavailable"}, status=503)
    # Idempotent logout: do not reveal if token existed or was revoked.
    return _security_headers(HttpResponse(status=204))
