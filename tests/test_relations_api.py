import pytest
from django.urls import reverse


def relation_payload(relation):
    return {
        "id": str(relation.id),
        "source": relation.source_id,
        "type": relation.type_id,
        "target": relation.target_id,
    }


@pytest.mark.django_db
def test_relation_list_returns_relations_in_semantic_order(client, curriculum_graph):
    response = client.get(reverse("relation-list"))

    expected = sorted(
        (relation_payload(relation) for relation in curriculum_graph["relations"].values()),
        key=lambda item: (item["source"], item["type"], item["target"], item["id"]),
    )

    assert response.status_code == 200
    assert response.json() == {"results": expected}


@pytest.mark.django_db
def test_relation_detail_returns_relation(client, curriculum_graph):
    relation = curriculum_graph["relations"][("matrix", "uses", "array")]

    response = client.get(reverse("relation-detail", kwargs={"relation_id": relation.id}))

    assert response.status_code == 200
    assert response.json() == relation_payload(relation)


@pytest.mark.django_db
def test_relation_detail_returns_404_for_unknown_id(client, curriculum_graph):
    import uuid

    response = client.get(reverse("relation-detail", kwargs={"relation_id": uuid.uuid4()}))

    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("parameter", "value", "expected_keys"),
    [
        ("source", "matrix", [("matrix", "subtype_of", "data-structure"), ("matrix", "uses", "array")]),
        ("type", "subtype_of", [("array", "subtype_of", "data-structure"), ("matrix", "subtype_of", "data-structure")]),
        ("target", "array", [("matrix", "uses", "array")]),
    ],
)
def test_relation_list_filters_by_semantic_fields(client, curriculum_graph, parameter, value, expected_keys):
    response = client.get(reverse("relation-list"), {parameter: value})

    expected = sorted(
        (relation_payload(curriculum_graph["relations"][key]) for key in expected_keys),
        key=lambda item: (item["source"], item["type"], item["target"], item["id"]),
    )

    assert response.status_code == 200
    assert response.json() == {"results": expected}


@pytest.mark.django_db
def test_relation_list_combines_filters(client, curriculum_graph):
    relation = curriculum_graph["relations"][("matrix", "subtype_of", "data-structure")]

    response = client.get(
        reverse("relation-list"),
        {"source": "matrix", "type": "subtype_of", "target": "data-structure"},
    )

    assert response.status_code == 200
    assert response.json() == {"results": [relation_payload(relation)]}


@pytest.mark.django_db
def test_relation_list_returns_empty_results_for_unmatched_filter(client, curriculum_graph):
    response = client.get(reverse("relation-list"), {"source": "missing"})

    assert response.status_code == 200
    assert response.json() == {"results": []}


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_relation_list_rejects_unsupported_methods(client, method):
    response = getattr(client, method)(reverse("relation-list"))

    assert response.status_code == 405


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_relation_detail_rejects_unsupported_methods(client, curriculum_graph, method):
    relation = curriculum_graph["relations"][("matrix", "uses", "array")]

    response = getattr(client, method)(
        reverse("relation-detail", kwargs={"relation_id": relation.id})
    )

    assert response.status_code == 405
