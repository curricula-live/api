import pytest
from django.urls import reverse


pytestmark = pytest.mark.django_db


def _semantic_relation(relation):
    return (relation["source"], relation["type"], relation["target"])


def test_concept_neighborhood_returns_incoming_and_outgoing_relations(
    client, curriculum_graph
):
    response = client.get(reverse("concept-neighborhood", args=["array"]))

    assert response.status_code == 200
    payload = response.json()
    assert payload["concept"] == {"slug": "array"}
    assert [_semantic_relation(relation) for relation in payload["outgoing"]] == [
        ("array", "subtype_of", "data-structure"),
    ]
    assert [_semantic_relation(relation) for relation in payload["incoming"]] == [
        ("matrix", "uses", "array"),
    ]


def test_concept_neighborhood_orders_relations_deterministically(client, curriculum_graph):
    response = client.get(reverse("concept-neighborhood", args=["data-structure"]))

    assert response.status_code == 200
    payload = response.json()
    assert payload["outgoing"] == []
    assert [_semantic_relation(relation) for relation in payload["incoming"]] == [
        ("array", "subtype_of", "data-structure"),
        ("matrix", "subtype_of", "data-structure"),
    ]


def test_concept_neighborhood_returns_empty_lists_for_isolated_concept(
    client, curriculum_graph
):
    from core.models import Concept

    Concept.objects.create(slug="isolated")

    response = client.get(reverse("concept-neighborhood", args=["isolated"]))

    assert response.status_code == 200
    assert response.json() == {
        "concept": {"slug": "isolated"},
        "outgoing": [],
        "incoming": [],
    }


def test_concept_neighborhood_returns_404_for_unknown_concept(client, curriculum_graph):
    response = client.get(reverse("concept-neighborhood", args=["missing"]))

    assert response.status_code == 404


def test_concept_neighborhood_rejects_unsupported_methods(client, curriculum_graph):
    response = client.post(reverse("concept-neighborhood", args=["array"]))

    assert response.status_code == 405
