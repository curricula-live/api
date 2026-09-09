import pytest
from django.urls import reverse


def test_api_root_describes_stable_public_contract(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "curricula.live API",
        "latest_version": "v1",
        "versions": {"v1": "/v1/"},
    }


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_api_root_rejects_unsupported_methods(client, method):
    response = getattr(client, method)("/")

    assert response.status_code == 405


@pytest.mark.django_db
def test_named_graph_routes_are_mounted_under_v1(client, curriculum_graph):
    assert reverse("concept-list") == "/v1/concepts/"
    assert reverse("relation-list") == "/v1/relations/"
    assert reverse("relation-type-list") == "/v1/relation-types/"

    response = client.get(reverse("concept-list"))
    assert response.status_code == 200


def test_legacy_api_prefix_is_not_part_of_public_contract(client):
    assert client.get("/api/concepts/").status_code == 404


def test_bare_resource_path_is_not_a_floating_alias(client):
    assert client.get("/concepts/").status_code == 404
