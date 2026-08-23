import uuid

import pytest
from django.urls import reverse

from core.models import Concept, Relation, RelationType


pytestmark = pytest.mark.django_db


@pytest.fixture
def prerequisite_graph(db):
    concepts = {
        slug: Concept.objects.create(slug=slug)
        for slug in ("a", "b", "c", "d", "target", "unrelated")
    }
    relation_type = RelationType.objects.create(slug="prerequisite_of")

    def connect(source, target):
        return Relation.objects.create(
            id=uuid.uuid4(),
            source=concepts[source],
            type=relation_type,
            target=concepts[target],
        )

    connect("a", "target")
    connect("b", "target")
    connect("c", "a")
    connect("d", "c")
    connect("target", "d")

    return concepts


def test_prerequisites_traverses_incoming_edges_breadth_first(client, prerequisite_graph):
    response = client.get(reverse("concept-prerequisites", args=["target"]), {"max_depth": 3})
    assert response.status_code == 200
    assert response.json()["results"] == [
        {"slug": "a", "depth": 1}, {"slug": "b", "depth": 1},
        {"slug": "c", "depth": 2}, {"slug": "d", "depth": 3},
    ]


def test_prerequisites_respects_depth_bound(client, prerequisite_graph):
    response = client.get(reverse("concept-prerequisites", args=["target"]), {"max_depth": 1})
    assert response.status_code == 200
    assert response.json()["results"] == [
        {"slug": "a", "depth": 1}, {"slug": "b", "depth": 1},
    ]


def test_prerequisites_respects_node_bound_and_reports_truncation(client, prerequisite_graph):
    response = client.get(reverse("concept-prerequisites", args=["target"]), {"max_nodes": 1})
    assert response.status_code == 200
    assert response.json()["results"] == [{"slug": "a", "depth": 1}]
    assert response.json()["truncated"] is True


def test_prerequisites_zero_node_bound_reports_omitted_prerequisites(client, prerequisite_graph):
    response = client.get(reverse("concept-prerequisites", args=["target"]), {"max_nodes": 0})
    assert response.status_code == 200
    assert response.json()["results"] == []
    assert response.json()["truncated"] is True


def test_prerequisites_zero_depth_is_not_truncated(client, prerequisite_graph):
    response = client.get(
        reverse("concept-prerequisites", args=["target"]), {"max_depth": 0, "max_nodes": 0}
    )
    assert response.status_code == 200
    assert response.json()["results"] == []
    assert response.json()["truncated"] is False


def test_prerequisites_handles_cycles_without_repeating_root(client, prerequisite_graph):
    response = client.get(reverse("concept-prerequisites", args=["target"]), {"max_depth": 10})
    slugs = [item["slug"] for item in response.json()["results"]]
    assert slugs == ["a", "b", "c", "d"]
    assert "target" not in slugs


def test_prerequisites_returns_empty_results_when_no_edges_exist(client, prerequisite_graph):
    response = client.get(reverse("concept-prerequisites", args=["unrelated"]))
    assert response.status_code == 200
    assert response.json()["results"] == []
    assert response.json()["truncated"] is False


@pytest.mark.parametrize(
    ("parameter", "value"),
    [("max_depth", "nope"), ("max_depth", "-1"), ("max_depth", "11"),
     ("max_nodes", "nope"), ("max_nodes", "-1"), ("max_nodes", "501")],
)
def test_prerequisites_rejects_invalid_bounds(client, prerequisite_graph, parameter, value):
    response = client.get(reverse("concept-prerequisites", args=["target"]), {parameter: value})
    assert response.status_code == 400


def test_prerequisites_returns_404_for_unknown_concept(client, prerequisite_graph):
    response = client.get(reverse("concept-prerequisites", args=["missing"]))
    assert response.status_code == 404


def test_prerequisites_rejects_unsupported_methods(client, prerequisite_graph):
    response = client.post(reverse("concept-prerequisites", args=["target"]))
    assert response.status_code == 405
