"""Fail-closed owner mail maintenance CLI tests; no database required."""
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from core.owner_mail_maintenance import maintenance_enabled, sweep_owner_mail

STAGING = {
    "APP_ENV": "staging",
    "IS_PRODUCTION": False,
    "OWNER_ASYNC_MAIL_ENABLED": True,
    "OWNER_EMAIL_WORKER_ENABLED": True,
}


@pytest.mark.parametrize("override", [
    {"OWNER_ASYNC_MAIL_ENABLED": False},
    {"OWNER_EMAIL_WORKER_ENABLED": False},
])
def test_cleanup_refuses_unsafe_environments(override):
    with override_settings(**{**STAGING, **override}):
        assert not maintenance_enabled()
        with pytest.raises(RuntimeError, match="disabled"):
            sweep_owner_mail()


@override_settings(**STAGING)
@pytest.mark.parametrize("batch", [0, -1, 1001, 1.5, "100"])
def test_invalid_batch_refused_before_sql(batch):
    with pytest.raises(ValueError, match="batch"):
        sweep_owner_mail(batch=batch)


@override_settings(**STAGING)
def test_management_command_requires_confirmation():
    with pytest.raises(CommandError, match="confirmation"):
        call_command("maintain_owner_mail", "--confirm", "wrong")


@override_settings(APP_ENV="production", IS_PRODUCTION=True,
                   OWNER_ASYNC_MAIL_ENABLED=True, OWNER_EMAIL_WORKER_ENABLED=True)
def test_production_cleanup_uses_distinct_confirmation():
    assert maintenance_enabled()
    with pytest.raises(CommandError, match="confirmation"):
        call_command("maintain_owner_mail", "--confirm", "MAINTAIN-STAGING-OWNER-MAIL")
