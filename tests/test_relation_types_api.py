import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_relation_type_list_returns_types_in_slug_order(client, curriculum_graph):
    response = client.get(reverse("relation-type-list"))

    assert response.status_code == 200
    assert response.json() == {
        "results": [
            {"slug": "subtype_of"},
            {"slug": "uses"},
        ]
    }


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_relation_type_list_rejects_unsupported_methods(client, method):
    response = getattr(client, method)(reverse("relation-type-list"))

    assert response.status_code == 405
