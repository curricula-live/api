import uuid

import pytest
from django.urls import reverse

from core.models import Concept, Relation, RelationType


@pytest.fixture
def search_graph(db):
    concepts = {
        slug: Concept.objects.create(slug=slug)
        for slug in (
            "binary",
            "binary-addition",
            "binary-numbers",
            "data-representation",
            "signed-integers",
            "twos-complement",
        )
    }
    relation_types = {
        slug: RelationType.objects.create(slug=slug)
        for slug in ("prerequisite_of", "related_to")
    }

    relation_specs = (
        ("binary-numbers", "prerequisite_of", "signed-integers"),
        ("signed-integers", "prerequisite_of", "twos-complement"),
        ("twos-complement", "related_to", "binary-numbers"),
    )
    relations = []
    for source_slug, type_slug, target_slug in relation_specs:
        relations.append(
            Relation.objects.create(
                id=uuid.uuid4(),
                source=concepts[source_slug],
                type=relation_types[type_slug],
                target=concepts[target_slug],
            )
        )

    return {"concepts": concepts, "relations": relations}


@pytest.mark.django_db
@pytest.mark.parametrize("params", [{}, {"q": ""}, {"q": "   "}])
def test_search_requires_non_blank_query(client, params):
    response = client.get(reverse("search"), params)

    assert response.status_code == 400


@pytest.mark.django_db
def test_search_concepts_prefers_exact_then_orders_partial_matches(client, search_graph):
    response = client.get(reverse("search"), {"q": "binary", "category": "concepts"})

    assert response.status_code == 200
    assert response.json() == {
        "query": "binary",
        "results": {
            "concepts": [
                {"slug": "binary"},
                {"slug": "binary-addition"},
                {"slug": "binary-numbers"},
            ]
        },
    }


@pytest.mark.django_db
def test_search_is_case_insensitive(client, search_graph):
    response = client.get(reverse("search"), {"q": "BINARY NUMBERS", "category": "concepts"})

    assert response.status_code == 200
    assert response.json()["results"]["concepts"][0] == {"slug": "binary-numbers"}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "query",
    ["two's complement", "two’s complement", "twos complement", "twos-complement"],
)
def test_search_normalizes_spaces_hyphens_and_apostrophes(client, search_graph, query):
    response = client.get(reverse("search"), {"q": query, "category": "concepts"})

    assert response.status_code == 200
    assert response.json()["results"]["concepts"] == [{"slug": "twos-complement"}]


@pytest.mark.django_db
def test_search_connections_matches_source_target_and_relation_type(client, search_graph):
    source_response = client.get(
        reverse("search"), {"q": "binary numbers", "category": "connections"}
    )
    target_response = client.get(
        reverse("search"), {"q": "signed integers", "category": "connections"}
    )
    type_response = client.get(
        reverse("search"), {"q": "prerequisite of", "category": "connections"}
    )

    assert source_response.status_code == 200
    assert len(source_response.json()["results"]["connections"]) == 2
    assert target_response.status_code == 200
    assert len(target_response.json()["results"]["connections"]) == 2
    assert type_response.status_code == 200
    assert len(type_response.json()["results"]["connections"]) == 2


@pytest.mark.django_db
def test_search_connection_is_returned_once_when_multiple_fields_match(client, db):
    concept = Concept.objects.create(slug="binary")
    relation_type = RelationType.objects.create(slug="binary")
    relation = Relation.objects.create(
        id=uuid.uuid4(),
        source=concept,
        type=relation_type,
        target=concept,
    )

    response = client.get(reverse("search"), {"q": "binary", "category": "connections"})

    assert response.status_code == 200
    connections = response.json()["results"]["connections"]
    assert connections == [
        {
            "id": str(relation.id),
            "source": "binary",
            "type": "binary",
            "target": "binary",
        }
    ]


@pytest.mark.django_db
def test_search_all_groups_concepts_and_connections(client, search_graph):
    response = client.get(reverse("search"), {"q": "binary"})

    assert response.status_code == 200
    assert set(response.json()["results"]) == {"concepts", "connections"}


@pytest.mark.django_db
def test_search_category_filter_omits_other_categories(client, search_graph):
    response = client.get(reverse("search"), {"q": "binary", "category": "connections"})

    assert response.status_code == 200
    assert set(response.json()["results"]) == {"connections"}


@pytest.mark.django_db
def test_search_rejects_invalid_category(client, search_graph):
    response = client.get(reverse("search"), {"q": "binary", "category": "curriculum"})

    assert response.status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize("limit", ["0", "101", "not-a-number"])
def test_search_rejects_invalid_limit(client, search_graph, limit):
    response = client.get(reverse("search"), {"q": "binary", "limit": limit})

    assert response.status_code == 400


@pytest.mark.django_db
def test_search_respects_requested_limit_per_category(client, search_graph):
    response = client.get(reverse("search"), {"q": "binary", "limit": 1})

    assert response.status_code == 200
    assert len(response.json()["results"]["concepts"]) == 1
    assert len(response.json()["results"]["connections"]) == 1


@pytest.mark.django_db
def test_search_default_limit_is_twenty(client, db):
    for index in range(25):
        Concept.objects.create(slug=f"searchable-{index:02d}")

    response = client.get(reverse("search"), {"q": "searchable", "category": "concepts"})

    assert response.status_code == 200
    assert len(response.json()["results"]["concepts"]) == 20


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_search_rejects_unsupported_methods(client, method):
    response = getattr(client, method)(reverse("search"), {"q": "binary"})

    assert response.status_code == 405
