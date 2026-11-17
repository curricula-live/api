"""Proof-path regression checks for synthetic class-expression inference."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from core.formal_class_inference import derive_conjunction_consequences

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "formal-array.synthetic.json"
ARRAY = "ea8c3f31-8745-52b1-9e29-d5fcf6ab16ba"
STRUCTURE = "50484348-83a3-57b8-bbe4-114b66419300"
INDEX = "b4bf30bd-361a-5121-99f9-2c18afeaa60e"
LABELS = {ARRAY: "Array", STRUCTURE: "Data Structure", INDEX: "Index"}


def model():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def infer(data):
    return derive_conjunction_consequences(
        data, concept_labels=LABELS, predicate_labels={"uses": "uses"},
        known_statement_ids=set(),
    )


def test_and_elimination_produces_only_two_conditional_conclusions_with_witnesses():
    outcome = infer(model())
    assert len(outcome["consequences"]) == 2
    by_name = {row["unicode"]: row for row in outcome["consequences"]}
    assert set(by_name) == {
        "Array ⊑ Data Structure",
        "Array ⊑ ∃uses.Index",
    }
    assert "Array ⊑ Index" not in by_name
    assert by_name["Array ⊑ Data Structure"]["proof_steps"] == [
        {"rule": "right_intersection_elimination", "argument_index": 0}
    ]
    assert by_name["Array ⊑ ∃uses.Index"]["proof_steps"] == [
        {"rule": "right_intersection_elimination", "argument_index": 1}
    ]
    assert all(c["premise_model"] == outcome["model_fingerprint"] for c in outcome["consequences"])
    assert outcome["may_publish"] is False
    assert all(c["scientific_claim_verified"] is False for c in outcome["consequences"])


def test_disjunction_is_not_split_into_claims():
    sample = model()
    sample["expression"]["op"] = "or"
    outcome = infer(sample)
    assert outcome["consequences"] == []


def test_negation_and_existential_restriction_are_not_interpreted_as_subclasses():
    sample = model()
    sample["expression"] = {
        "op": "some", "property": "uses",
        "filler": {"op": "concept", "concept_id": INDEX}
    }
    assert infer(sample)["consequences"] == []
    sample["expression"] = {
        "op": "not", "arg": {"op": "concept", "concept_id": INDEX}
    }
    assert infer(sample)["consequences"] == []


def test_equivalence_yields_valid_left_to_right_witness_before_and_elimination():
    sample = model()
    sample["relation"] = "equivalent"
    outcome = infer(sample)
    assert len(outcome["consequences"]) == 2
    assert outcome["consequences"][0]["proof_steps"][0] == {
        "rule": "equivalence_to_subsumption",
    }
    assert "equivalence_to_subsumption" in outcome["applied_rules"]


def test_nested_intersections_preserve_premise_path_and_deduplicate_results():
    sample = model()
    ref = {"op": "concept", "concept_id": STRUCTURE}
    some = {"op": "some", "property": "uses", "filler": {"op": "concept", "concept_id": INDEX}}
    sample["expression"] = {
        "op": "and",
        "args": [
            {"op": "and", "args": [ref, some]},
            ref,
        ],
    }
    outcome = infer(sample)
    assert len(outcome["consequences"]) == 2
    assert outcome["consequences"][0]["proof_steps"] == [
        {"rule": "right_intersection_elimination", "argument_index": 0},
        {"rule": "right_intersection_elimination", "argument_index": 0},
    ]
    assert outcome == infer(deepcopy(sample))
