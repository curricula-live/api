"""Legacy concept-page projection tests: provenance, bounds and sound rule witnesses."""
import uuid

import pytest
from django.urls import reverse

from core.models import Concept, Relation

pytestmark = pytest.mark.django_db


def _url(slug="array"):
    return reverse("concept-documentation", args=[slug])


def _add(graph, subject, predicate, target):
    for slug in (subject, target):
        if slug not in graph["concepts"]:
            graph["concepts"][slug] = Concept.objects.create(slug=slug)
    if predicate not in graph["relation_types"]:
        from core.models import RelationType
        graph["relation_types"][predicate] = RelationType.objects.create(slug=predicate)
    return Relation.objects.create(
        id=uuid.uuid4(),
        source=graph["concepts"][subject],
        type=graph["relation_types"][predicate],
        target=graph["concepts"][target],
    )


def test_documentation_uses_existing_graph_not_fixture_definitions(client, curriculum_graph):
    response = client.get(_url())
    assert response.status_code == 200
    page = response.json()
    assert page["source"]["kind"] == "legacy_concept_relation_tables"
    assert page["source"]["is_published_v2"] is False
    assert page["source"]["is_peer_reviewed"] is False
    assert page["traversal"]["depth"] == 2
    assert page["characterization"]["text"] == "Array is a data structure."
    assert len(page["characterization"]["assertion_ids"]) == 1
    assert len(page["asserted_statements"]) == 3
    assert page["relation_profile"]["direct_recorded_relations"] == sum(
        1 for edge in page["asserted_statements"]
        if edge["source"] == "array" or edge["target"] == "array"
    )
    assert page["relation_profile"]["scope"] == "retrieved_neighborhood_only"
    assert page["relation_profile"]["scientific_completeness_established"] is False
    assert page["derived_statements"] == []
    assert response["Cache-Control"] == "no-store"


def test_subtype_transitivity_has_exact_premise_uuids(client, curriculum_graph):
    one = _add(curriculum_graph, "array", "subtype_of", "collection")
    two = _add(curriculum_graph, "collection", "subtype_of", "sequence")
    response = client.get(_url() + "?depth=2")
    page = response.json()
    proof = next(row for row in page["derived_statements"] if row["target"] == "sequence")
    assert proof["premise_ids"] == [str(one.id), str(two.id)]
    assert proof["rule"] == "subtype_of_transitivity"
    assert proof["status"] == "conditional_provisional_inference"
    assert proof["text"] == "Array is a sequence."
    assert set(proof["premise_ids"]) <= {edge["id"] for edge in page["asserted_statements"]}


def test_depth_one_does_not_derive_two_hop_facts(client, curriculum_graph):
    _add(curriculum_graph, "array", "subtype_of", "collection")
    _add(curriculum_graph, "collection", "subtype_of", "sequence")
    page = client.get(_url() + "?depth=1").json()
    assert "sequence" not in {node["slug"] for node in page["graph"]["nodes"]}
    assert page["derived_statements"] == []


def test_three_hop_path_witness_is_ordered_and_no_phantom_direct_edges(client, curriculum_graph):
    first = _add(curriculum_graph, "array", "subtype_of", "collection")
    second = _add(curriculum_graph, "collection", "subtype_of", "sequence")
    third = _add(curriculum_graph, "sequence", "subtype_of", "container")
    page = client.get(_url() + "?depth=3").json()
    conclusion = next(d for d in page["derived_statements"] if d["target"] == "container")
    assert conclusion["premise_ids"] == [str(first.id), str(second.id), str(third.id)]
    proof = conclusion["proof"]
    assert proof["format"] == "provisional-subtype-trace@1"
    assert proof["scope_origin"] == "assumed_not_in_source"
    assert proof["source_semantics_verified"] is False
    assert proof["is_formal_proof_certificate"] is False
    assert proof["may_publish"] is False
    assert [step["id"] for step in proof["steps"]] == ["h1", "h2", "h3", "s1", "s2"]
    assert [step["assertion_id"] for step in proof["steps"][:3]] == [
        str(first.id), str(second.id), str(third.id)
    ]
    assert proof["steps"][3]["depends_on"] == ["h1", "h2"]
    assert proof["steps"][4]["depends_on"] == ["s1", "h3"]
    assert proof["steps"][4]["target"] == "container"
    assert proof["conclusion_step_id"] == "s2"
    assert not any(edge["source"] == "array" and edge["target"] == "container"
                   for edge in page["asserted_statements"])


def test_five_hops_reach_longer_subtype_chains(client, curriculum_graph):
    first = "array"
    edge_ids = []
    for level in range(1, 6):
        next_slug = f"level-{level}"
        edge_ids.append(str(_add(curriculum_graph, first, "subtype_of", next_slug).id))
        first = next_slug
    short = client.get(_url() + "?depth=2").json()
    deep = client.get(_url() + "?depth=5").json()
    assert "level-5" not in {node["slug"] for node in short["graph"]["nodes"]}
    assert "level-5" in {node["slug"] for node in deep["graph"]["nodes"]}
    witness = next(row for row in deep["derived_statements"] if row["target"] == "level-5")
    assert witness["premise_ids"] == edge_ids
    assert deep["traversal"]["depth"] == 5


def test_uses_and_part_of_never_promoted_to_subtype_or_indexed_access(client, curriculum_graph):
    _add(curriculum_graph, "array", "uses", "matrix")
    # The shared curriculum_graph fixture already records matrix subtype_of data-structure.
    page = client.get(_url() + "?depth=3").json()
    assert "Array uses matrix." in [e["text"] for e in page["asserted_statements"]]
    assert page["derivation_policy"]["uses_implies_indexed_access"] is False
    assert page["derivation_policy"]["uses_implies_prerequisite"] is False
    assert all(d["target"] != "matrix" for d in page["derived_statements"])


def test_no_invented_definition_when_no_subtype(client, curriculum_graph):
    from core.models import Concept
    Concept.objects.create(slug="isolated")
    page = client.get(_url("isolated")).json()
    assert page["characterization"] is None
    assert page["graph"] == {"nodes": [{"slug": "isolated", "label": "Isolated", "hop": 0}],
                             "edges": []}


@pytest.mark.parametrize("query", ["?depth=0", "?depth=6", "?depth=x", "?depth=1.4"])
def test_rejects_invalid_depth(client, curriculum_graph, query):
    assert client.get(_url() + query).status_code == 400


def test_not_found_and_method_restrictions(client, curriculum_graph):
    assert client.get(_url("does-not-exist")).status_code == 404
    assert client.post(_url()).status_code == 405


def test_cycle_cannot_prove_a_concept_is_its_own_subtype(client, curriculum_graph):
    _add(curriculum_graph, "data-structure", "subtype_of", "array")
    page = client.get(_url() + "?depth=3").json()
    assert all(d["target"] != "array" for d in page["derived_statements"])


def test_query_count_scales_with_depth_not_total_neighbors(client, curriculum_graph, django_assert_max_num_queries):
    # A multi-branch graph still requires one concept-existence read and one
    # batched relation lookup per hop, instead of one query per discovered node.
    for index in range(35):
        middle = f"neighbor-{index:02}"
        _add(curriculum_graph, "array", "uses", middle)
        _add(curriculum_graph, middle, "subtype_of", f"category-{index:02}")
    with django_assert_max_num_queries(4):
        response = client.get(_url() + "?depth=3")
    assert response.status_code == 200
    page = response.json()
    assert len(page["graph"]["edges"]) >= 70
    assert len(page["graph"]["nodes"]) > 35
    assert page["source"]["is_published_v2"] is False


def test_proof_relevant_subtype_kept_when_graph_budget_is_exhausted(client, curriculum_graph):
    # Without predicate-aware ordering, many 'part_of' links can fill the
    # node budget before one important subtype classification is examined.
    for index in range(160):
        _add(curriculum_graph, "array", "part_of", f"filler-{index:03}")
    classification = _add(curriculum_graph, "array", "subtype_of", "important-category")
    page = client.get(_url() + "?depth=1").json()
    assert page["traversal"]["truncated"] is True
    assert "important-category" in {node["slug"] for node in page["graph"]["nodes"]}
    assert str(classification.id) in {row["id"] for row in page["asserted_statements"]}


def test_bounded_graph_reports_truncation(client, curriculum_graph):
    for index in range(255):
        _add(curriculum_graph, "array", "uses", f"neighbor-{index:02}")
    page = client.get(_url() + "?depth=3").json()
    assert page["traversal"]["truncated"] is True
    assert len(page["graph"]["nodes"]) <= page["traversal"]["max_nodes"]
    assert len(page["graph"]["edges"]) <= page["traversal"]["max_edges"]
    assert all(edge["source"] in {n["slug"] for n in page["graph"]["nodes"]}
               and edge["target"] in {n["slug"] for n in page["graph"]["nodes"]}
               for edge in page["graph"]["edges"])
