"""Recorded canonical relation UUIDs can safely name conditional proof atoms."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from core.formal_recorded_statement_bridge import (
    RecordedStatementBindingError,
    verify_recorded_statement_proof,
)

HERE = Path(__file__).resolve().parent
BINDING = HERE / "fixtures" / "recorded-array-bindings.synthetic.json"
PROOF = HERE / "fixtures" / "recorded-array-conjunction.synthetic.json"

ARRAY = "ea8c3f31-8745-52b1-9e29-d5fcf6ab16ba"
COLLECTION = "c5c9fcca-3db2-56f9-bceb-ec4dabd6ee78"
DATA = "2bfccfc4-b578-5dad-a6b2-361106b178b0"
ARRAY_COLLECTION = "048adf33-0701-43de-998f-20c299388f51"
COLLECTION_DATA = "15ead31d-e970-4aad-a4f8-7c9fccf3097a"


def _jsonl(rows):
    return b"".join(
        json.dumps(row, separators=(",", ":"), sort_keys=True).encode() + b"\n"
        for row in rows
    )


def local_snapshot():
    # Minimal disposable source records with the exact canonical UUIDs.
    # These are test snapshots, not an alternate authoritative corpus.
    concepts = _jsonl([
        {"id": ARRAY, "label": "Array", "slug": "array"},
        {"id": COLLECTION, "label": "Collection", "slug": "collection"},
        {"id": DATA, "label": "Data", "slug": "data"},
    ])
    statements = _jsonl([
        {
            "id": ARRAY_COLLECTION, "predicate": "subtype_of",
            "subject": {"kind": "concept", "id": ARRAY},
            "object": {"kind": "concept", "id": COLLECTION},
        },
        {
            "id": COLLECTION_DATA, "predicate": "subtype_of",
            "subject": {"kind": "concept", "id": COLLECTION},
            "object": {"kind": "concept", "id": DATA},
        },
    ])
    return concepts, statements


def sample():
    proof = json.loads(PROOF.read_text(encoding="utf-8"))
    binding = json.loads(BINDING.read_text(encoding="utf-8"))
    concepts, statements = local_snapshot()
    binding["snapshot"] = {
        "concepts_sha256": "sha256:" + sha256(concepts).hexdigest(),
        "statements_sha256": "sha256:" + sha256(statements).hexdigest(),
    }
    return proof, binding, concepts, statements


def verify(proof, bindings, concepts, statements):
    return verify_recorded_statement_proof(
        proof, bindings,
        concepts_jsonl=concepts, statements_jsonl=statements,
    )


def test_real_uuids_bind_atomic_hypotheses_without_inventing_graph_consequences():
    proof, bindings, concepts, statements = sample()
    result = verify(proof, bindings, concepts, statements)
    assert result["logical_status"] == "conditional_on_recorded_statements"
    assert result["propositional_steps_verified"] is True
    assert result["propositional_proof"]["conclusion"]["unicode"] == "P ∧ Q"
    assert result["propositional_proof"]["open_assumption_step_ids"] == ["h1", "h2"]
    assert result["semantic_graph_rules_applied"] == []
    assert result["derived_graph_relations"] == []
    assert result["scientific_claims_verified"] is False
    assert result["authorizes_new_canonical_claim"] is False
    assert result["may_publish"] is False
    assert {
        (r["atom"], r["recorded_claim_text"], r["scientific_status"])
        for r in result["atom_bindings"]
    } == {
        ("P", "Array subtype_of Collection", "recorded_not_reviewed"),
        ("Q", "Collection subtype_of Data", "recorded_not_reviewed"),
    }
    assert [(r["assumption_step_id"], r["statement_id"]) for r in result["open_recorded_assumptions"]] == [
        ("h1", ARRAY_COLLECTION), ("h2", COLLECTION_DATA),
    ]
    assert result == verify(deepcopy(proof), deepcopy(bindings), concepts, statements)


@pytest.mark.parametrize("mutate", [
    lambda p, b: b["snapshot"].update({"statements_sha256": "sha256:" + "0" * 64}),
    lambda p, b: b["snapshot"].update({"concepts_sha256": "sha256:" + "0" * 64}),
    lambda p, b: b["snapshot"].update({"unexpected": "extra"}),
    lambda p, b: b["provenance"].update({"status": "accepted"}),
    lambda p, b: b["provenance"].update({"source_scientific_review": "approved"}),
    lambda p, b: b.update({"scope": "scientific_universal"}),
    lambda p, b: b["bindings"].append(deepcopy(b["bindings"][0])),
    lambda p, b: b["bindings"].append({"atom": "R", "statement_id": ARRAY_COLLECTION}),
    lambda p, b: b["bindings"][1].update({"statement_id": "00000000-0000-4000-8000-000000000000"}),
    lambda p, b: b["bindings"][0].update({"atom": "not_a_formal_atom"}),
    lambda p, b: b["bindings"][0].update({"predicate": "subtype_of"}),
    lambda p, b: b["bindings"].pop(),
    lambda p, b: p["steps"][2].update({"left": "nonexistent"}),
    lambda p, b: p.update({"goal": {"op": "atom", "name": "R"}}),
])
def test_invalid_mapping_or_proof_fails_closed(mutate):
    proof, bindings, concepts, statements = sample()
    mutate(proof, bindings)
    with pytest.raises(RecordedStatementBindingError):
        verify(proof, bindings, concepts, statements)


def test_unmapped_atoms_are_not_accepted_as_informal_external_facts():
    proof, bindings, concepts, statements = sample()
    proof["goal"] = {"op": "or", "left": proof["goal"], "right": {"op": "atom", "name": "R"}}
    proof["steps"].append({
        "id": "s2", "rule": "or_intro_left", "premise": "s1",
        "other": {"op": "atom", "name": "R"},
    })
    proof["conclusion_step_id"] = "s2"
    with pytest.raises(RecordedStatementBindingError, match="Atom mapping differs"):
        verify(proof, bindings, concepts, statements)


def test_bound_atoms_are_not_promoted_to_scientific_axioms_in_closed_tautology():
    proof, bindings, concepts, statements = sample()
    P = {"op": "atom", "name": "P"}
    proof["goal"] = {"op": "implies", "left": P, "right": P}
    proof["steps"] = [
        {"id": "h1", "rule": "assume", "formula": P},
        {"id": "s1", "rule": "imp_intro", "assumption": "h1", "conclusion": "h1"},
    ]
    proof["conclusion_step_id"] = "s1"
    bindings["bindings"] = bindings["bindings"][:1]
    result = verify(proof, bindings, concepts, statements)
    assert result["logical_status"] == "closed_synthetic_propositional_theorem"
    assert result["open_recorded_assumptions"] == []
    assert result["scientific_claims_verified"] is False


def test_complex_assumption_cannot_claim_it_is_one_recorded_statement():
    proof, bindings, concepts, statements = sample()
    proof["steps"] = [
        {"id": "h1", "rule": "assume", "formula": proof["goal"]}
    ]
    proof["conclusion_step_id"] = "h1"
    with pytest.raises(RecordedStatementBindingError, match="atomic assumption"):
        verify(proof, bindings, concepts, statements)


def test_literal_statement_cannot_be_silently_treated_as_concept_relation():
    proof, bindings, concepts, statements = sample()
    rows = [json.loads(line) for line in statements.splitlines()]
    rows[0]["object"] = {"kind": "literal", "datatype": "string", "value": "42"}
    statements = _jsonl(rows)
    bindings["snapshot"]["statements_sha256"] = "sha256:" + sha256(statements).hexdigest()
    with pytest.raises(RecordedStatementBindingError, match="concept-to-concept"):
        verify(proof, bindings, concepts, statements)


def test_other_than_propositional_connective_no_subtype_transitivity_occurs():
    proof, bindings, concepts, statements = sample()
    result = verify(proof, bindings, concepts, statements)
    text = json.dumps(result, ensure_ascii=False)
    assert "Array subtype_of Data" not in text
    assert "subtype_transitivity" not in text
