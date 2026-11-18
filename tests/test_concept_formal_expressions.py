"""Sort-aware formal projection of recorded subtype conditions and rule implications."""
from __future__ import annotations

from copy import deepcopy
import uuid

import pytest
from django.urls import reverse

from core.concept_formal_expressions import direct_class_conditions, transitivity_formula
from core.models import Concept, Relation, RelationType

pytestmark = pytest.mark.django_db


def relation(source: str, target: str, predicate: str = "subtype_of"):
    a, _ = Concept.objects.get_or_create(slug=source)
    b, _ = Concept.objects.get_or_create(slug=target)
    t, _ = RelationType.objects.get_or_create(slug=predicate)
    return Relation.objects.create(
        id=uuid.uuid4(), source=a, type=t, target=b
    )


def get(client, slug="sample", depth=3):
    return client.get(reverse("concept-documentation", args=[slug]) + f"?depth={depth}").json()


def test_direct_subtype_conjunction_is_necessary_not_equivalence(client):
    first = relation("sample", "collection")
    second = relation("sample", "data-structure")
    relation("sample", "index", "uses")
    page = get(client)
    formal = page["class_conditions"]
    assert formal["kind"] == "necessary_class_condition"
    assert formal["expression"] == {
        "op": "subsumption",
        "left": {"op": "concept", "slug": "sample"},
        "right": {
            "op": "intersection",
            "args": [
                {"op": "concept", "slug": "collection"},
                {"op": "concept", "slug": "data-structure"},
            ],
        },
    }
    assert formal["assertion_ids"] == [str(first.id), str(second.id)]
    assert formal["equivalence_established"] is False
    assert formal["source_semantics_verified"] is False
    assert "class_equivalence" not in str(page)
    assert '"iff"' not in str(page)
    assert formal["status"] == "conditional_on_recorded_assertions"


def test_one_direct_superclass_does_not_force_an_intersection(client):
    relation("singleton", "collection")
    assert get(client, "singleton")["class_conditions"] is None


def test_uses_and_part_of_do_not_create_class_axioms_or_implications(client):
    relation("unclassified", "index", "uses")
    relation("index", "unclassified", "part_of")
    page = get(client, "unclassified")
    assert page["class_conditions"] is None
    assert page["derived_statements"] == []


def test_transitive_rule_is_a_typed_propositional_implication(client):
    first = relation("sample", "collection")
    second = relation("collection", "data")
    page = get(client)
    derived = next(row for row in page["derived_statements"] if row["target"] == "data")
    formula = derived["formal_rule"]
    assert formula["kind"] == "conditional_rule_formula"
    assert formula["rule"] == "subtype_of_transitivity"
    assert formula["assertion_ids"] == [str(first.id), str(second.id)]
    assert formula["expression"] == {
        "op": "implies",
        "left": {
            "op": "and",
            "args": [
                {
                    "op": "subsumption",
                    "left": {"op": "concept", "slug": "sample"},
                    "right": {"op": "concept", "slug": "collection"},
                },
                {
                    "op": "subsumption",
                    "left": {"op": "concept", "slug": "collection"},
                    "right": {"op": "concept", "slug": "data"},
                },
            ],
        },
        "right": {
            "op": "subsumption",
            "left": {"op": "concept", "slug": "sample"},
            "right": {"op": "concept", "slug": "data"},
        },
    }
    assert formula["source_semantics_verified"] is False
    assert formula["equivalence_established"] is False


def test_three_hop_rule_keeps_all_three_recorded_atoms(client):
    first = relation("sample", "collection")
    second = relation("collection", "data")
    third = relation("data", "value")
    page = get(client, depth=3)
    derived = next(row for row in page["derived_statements"] if row["target"] == "value")
    formula = derived["formal_rule"]
    assert len(formula["expression"]["left"]["args"]) == 3
    assert formula["assertion_ids"] == [str(first.id), str(second.id), str(third.id)]


def test_malformed_proof_never_emits_implication():
    valid = {
        "subject": "array", "target": "data",
        "premise_ids": ["original-1", "original-2"],
        "proof": {
            "rule_application_checked": True,
            "source_semantics_verified": False,
            "conclusion_step_id": "s1",
            "steps": [
                {"id": "h1", "kind": "recorded_premise",
                 "subject": "array", "target": "collection",
                 "assertion_id": "original-1"},
                {"id": "h2", "kind": "recorded_premise",
                 "subject": "collection", "target": "data",
                 "assertion_id": "original-2"},
                {"id": "s1", "kind": "derived_step",
                 "subject": "array", "predicate": "subtype_of", "target": "data"},
            ],
        },
    }
    assert transitivity_formula(valid)["expression"]["op"] == "implies"
    altered = deepcopy(valid)
    altered["proof"]["steps"][-1]["target"] = "other"
    with pytest.raises(ValueError):
        transitivity_formula(altered)
    altered = deepcopy(valid)
    altered["premise_ids"].reverse()
    with pytest.raises(ValueError):
        transitivity_formula(altered)
    altered = deepcopy(valid)
    altered["proof"]["source_semantics_verified"] = True
    with pytest.raises(ValueError):
        transitivity_formula(altered)
