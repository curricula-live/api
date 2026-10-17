"""Reconstruct short-lived owner email challenges without storing bearer links.

A random challenge UUID is HMAC'd under a dedicated 256-bit+ private key.
Never reuse the rate-limit key or a Django/BFF signing key for this purpose.
The persistent DB contains only challenge IDs and purpose-separated token hashes.
Key rotation invalidates queued challenges; the worker discards mismatched jobs.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
from uuid import UUID

from django.conf import settings

_DOMAIN = b"curricula:owner-email-challenge:v1\x00"


def derive_owner_email_token(challenge_id: UUID, *, key: str | None = None) -> str:
    if not isinstance(challenge_id, UUID):
        raise TypeError("challenge identifier must be UUID")
    material = getattr(settings, "OWNER_EMAIL_TOKEN_KEY", "") if key is None else key
    if not isinstance(material, str) or len(material.encode("utf-8")) < 32:
        raise ValueError("owner email derivation key unavailable")
    digest = hmac.new(material.encode("utf-8"), _DOMAIN + challenge_id.bytes, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
