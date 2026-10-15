"""Feature-gated read-only verification endpoint for the owner admin BFF.

This route does not issue sessions. All credentials must be created via the
future reviewed POST-only passwordless flow. Neither body nor query parameters
may assert owner identity; a DB lookup is mandatory for every authorized read.
"""
from __future__ import annotations

from django.conf import settings
from django.db import DatabaseError
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET

from core.owner_auth_repository import find_verified_owner_session
from core.owner_session_contract import fingerprint_token


def _json(body: dict, status: int) -> JsonResponse:
    response = JsonResponse(body, status=status)
    response["Cache-Control"] = "private, no-store"
    response["Vary"] = "Authorization"
    return response


@require_GET
def verify_owner_session(request):
    if not getattr(settings, "OWNER_AUTH_ENABLED", False):
        raise Http404("Not available")

    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return _json({"error": "unauthorized"}, 401)
    credential = authorization[len("Bearer "):]
    try:
        digest = fingerprint_token(credential, "session")
    except (TypeError, ValueError):
        return _json({"error": "unauthorized"}, 401)

    try:
        attestation = find_verified_owner_session(digest)
    except DatabaseError:
        # Never fall back to a trusted-header owner flag or expose SQL.
        return _json({"error": "authentication unavailable"}, 503)

    if attestation is None:
        return _json({"error": "unauthorized"}, 401)
    return _json(attestation, 200)
