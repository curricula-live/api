import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_concept_list_returns_concepts_in_slug_order(client, curriculum_graph):
    response = client.get(reverse("concept-list"))

    assert response.status_code == 200
    assert response.json() == {
        "results": [
            {"slug": "array"},
            {"slug": "data-structure"},
            {"slug": "matrix"},
        ]
    }


@pytest.mark.django_db
def test_concept_detail_returns_concept(client, curriculum_graph):
    response = client.get(reverse("concept-detail", kwargs={"slug": "array"}))

    assert response.status_code == 200
    assert response.json() == {"slug": "array"}


@pytest.mark.django_db
def test_concept_detail_returns_404_for_unknown_slug(client, curriculum_graph):
    response = client.get(reverse("concept-detail", kwargs={"slug": "missing"}))

    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_concept_list_rejects_unsupported_methods(client, method):
    response = getattr(client, method)(reverse("concept-list"))

    assert response.status_code == 405


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_concept_detail_rejects_unsupported_methods(client, curriculum_graph, method):
    response = getattr(client, method)(
        reverse("concept-detail", kwargs={"slug": "array"})
    )

    assert response.status_code == 405
