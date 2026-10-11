"""Purpose-separated HMAC challenge derivation never stores the raw token."""
from uuid import uuid4

import pytest
from django.test import override_settings

from core.owner_mail_crypto import derive_owner_email_token
from core.owner_session_contract import fingerprint_token

KEY = "isolated-unit-only-dedicated-owner-mail-key-material"


def test_deterministic_derivation_is_url_safe_purpose_separated_and_keyed():
    identifier = uuid4()
    a = derive_owner_email_token(identifier, key=KEY)
    assert a == derive_owner_email_token(identifier, key=KEY)
    assert len(a) == 43
    assert a.isascii() and all(ch.isalnum() or ch in "_-" for ch in a)
    assert a != derive_owner_email_token(uuid4(), key=KEY)
    assert a != derive_owner_email_token(identifier, key=KEY + "rotated")
    assert len(fingerprint_token(a, "challenge")) == 64


def test_derivation_fails_closed_without_strong_key():
    identifier = uuid4()
    with pytest.raises(ValueError, match="unavailable"):
        derive_owner_email_token(identifier, key="short")
    with override_settings(OWNER_EMAIL_TOKEN_KEY=""):
        with pytest.raises(ValueError, match="unavailable"):
            derive_owner_email_token(identifier)
    with pytest.raises(TypeError, match="UUID"):
        derive_owner_email_token("not-a-uuid", key=KEY)
