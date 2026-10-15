"""Production release gate and bounded anonymous knowledge contract."""
from unittest.mock import patch
from uuid import UUID

from django.test import override_settings
from django.urls import reverse

COMMIT = "c83cf9229eeae4be2c67b95931020c8ca74b8d16"
OS = UUID("c74fe051-ac5e-521b-8770-3180fb0decb6")


def test_public_v2_disabled_without_explicit_release(client):
    with override_settings(PUBLIC_V2_ENABLED=False, PUBLIC_V2_RELEASE_COMMIT=COMMIT):
        assert client.get(reverse("v2-concepts")).status_code == 404
    with override_settings(PUBLIC_V2_ENABLED=True, PUBLIC_V2_RELEASE_COMMIT=""):
        assert client.get(reverse("v2-concepts")).status_code == 404


def test_invalid_search_and_page_never_touch_database(client):
    with patch("core.public_v2.connection.cursor") as cursor:
        for query in ("?limit=0", "?limit=101", "?offset=-1", "?offset=10001", "?q=x"):
            assert client.get(reverse("v2-concepts") + query).status_code == 400
        cursor.assert_not_called()


def test_release_mismatch_denies_all_public_reads(client):
    with override_settings(PUBLIC_V2_ENABLED=True, PUBLIC_V2_RELEASE_COMMIT=COMMIT):
        with patch("core.public_v2.connection.cursor") as cursor:
            sql = cursor.return_value.__enter__.return_value
            sql.fetchone.return_value = ("0" * 40,)
            for url in (reverse("v2-concepts"), reverse("v2-concept-detail", kwargs={"concept_id": OS}),
                        reverse("v2-concept-statements", kwargs={"concept_id": OS})):
                response = client.get(url)
                assert response.status_code == 503
                assert response["Cache-Control"] == "no-store"
            assert sql.execute.call_count == 3


def test_public_v2_is_get_only(client):
    assert client.post(reverse("v2-concepts")).status_code == 405
