"""Exact allowlist for a *disposable* HTTPS loopback fixture.

The public owner hostname continues to be exact and production POST handlers
remain disabled. Arbitrary preview URLs and staging wildcard hosts are denied.
"""
from django.test import override_settings

from core.owner_auth_http import _link_destination, _configured


@override_settings(APP_ENV="staging", IS_PRODUCTION=False)
def test_staging_tls_loopback_link_is_exact():
    with override_settings(OWNER_LOGIN_LINK_BASE="https://localhost:3443/login/verify"):
        assert _link_destination() == "https://localhost:3443/login/verify"


@override_settings(APP_ENV="staging", IS_PRODUCTION=False)
def test_no_arbitrary_hosts_ports_userinfo_or_redirects():
    invalid = (
        "https://localhost:3444/login/verify",
        "https://127.0.0.1:3443/login/verify",
        "https://localhost.evil.example:3443/login/verify",
        "https://localhost:3443/login/verify?redirect=https://evil.example",
        "https://user:pass@localhost:3443/login/verify",
        "https://localhost:3443/login/verify#injected",
        "http://localhost:3443/login/verify",
        "https://localhost:3443/login",
        "https://admin.curricula.live.evil.example/login/verify",
    )
    for target in invalid:
        with override_settings(OWNER_LOGIN_LINK_BASE=target):
            assert _link_destination() is None, target


@override_settings(APP_ENV="production", IS_PRODUCTION=True,
                   OWNER_LOGIN_LINK_BASE="https://localhost:3443/login/verify")
def test_fixture_origin_unusable_in_production():
    assert _link_destination() is None
    assert _configured() is False


@override_settings(APP_ENV="development", IS_PRODUCTION=False,
                   OWNER_LOGIN_LINK_BASE="https://localhost:3443/login/verify")
def test_fixture_origin_unusable_in_development():
    assert _link_destination() is None


@override_settings(APP_ENV="production", IS_PRODUCTION=True,
                   OWNER_LOGIN_LINK_BASE="https://admin.curricula.live/login/verify")
def test_production_link_allowlisted_but_post_auth_remains_disabled():
    assert _link_destination() == "https://admin.curricula.live/login/verify"
    assert _configured() is False
