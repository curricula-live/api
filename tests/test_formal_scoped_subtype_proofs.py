"""Only correctly typed, correctly scoped subtype paths can be inferred."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from core.formal_scoped_subtype_proofs import (
    ScopedSubtypeProofError, verify_scoped_subtype_proof,
)

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures/scoped-array-subtype.synthetic.json"

ARRAY = "ea8c3f31-8745-52b1-9e29-d5fcf6ab16ba"
COLLECTION = "c5c9fcca-3db2-56f9-bceb-ec4dabd6ee78"
DATA = "2bfccfc4-b578-5dad-a6b2-361106b178b0"
EXTRA = "00000000-0000-4000-8000-000000000004"
AB = "048adf33-0701-43de-998f-20c299388f51"
BC = "15ead31d-e970-4aad-a4f8-7c9fccf3097a"
CD = "00000000-0000-4000-8000-000000000008"
SCOPE = "hypothetical_shared_taxonomy"


def rows_bytes(rows):
    return b"".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        for row in rows
    )


def snapshot():
    concept_rows = [
        {"id": ARRAY, "label": "Array", "slug": "array"},
        {"id": COLLECTION, "label": "Collection", "slug": "collection"},
        {"id": DATA, "label": "Data", "slug": "data"},
    ]
    statement_rows = [
        {
            "id": AB, "subject": {"kind": "concept", "id": ARRAY},
            "predicate": "subtype_of",
            "object": {"kind": "concept", "id": COLLECTION},
        },
        {
            "id": BC, "subject": {"kind": "concept", "id": COLLECTION},
            "predicate": "subtype_of",
            "object": {"kind": "concept", "id": DATA},
        },
    ]
    return concept_rows, statement_rows


def sample():
    proof = json.loads(FIXTURE.read_text(encoding="utf-8"))
    concepts, statements = snapshot()
    return proof, concepts, statements


def verify(proof, concepts, statements):
    concept_bytes = rows_bytes(concepts)
    statement_bytes = rows_bytes(statements)
    # Test fixtures intentionally use a synthetic snapshot whose bytes
    # differ from the real canonical Git data; pin the exact local bytes.
    proof["snapshot"] = {
        "concepts_sha256": "sha256:" + sha256(concept_bytes).hexdigest(),
        "statements_sha256": "sha256:" + sha256(statement_bytes).hexdigest(),
    }
    return verify_scoped_subtype_proof(
        proof, concepts_jsonl=concept_bytes, statements_jsonl=statement_bytes,
    )


def test_real_recorded_uuid_witnesses_yield_conditional_array_subtype_data():
    proof, concepts, statements = sample()
    result = verify(proof, concepts, statements)
    assert result["conclusion"]["subject_concept_id"] == ARRAY
    assert result["conclusion"]["object_concept_id"] == DATA
    assert result["conclusion"]["predicate"] == "subtype_of"
    assert result["conclusion"]["scope"] == SCOPE
    assert result["conclusion"]["status"] == "conditional_provisional_inference"
    assert result["original_recorded_premises"] == [AB, BC]
    assert result["rule_id"] == "subtype_transitivity@v0"
    assert result["steps"][-1]["premise_step_ids"] == ["h1", "h2"]
    assert result["scope_origin"] == "assumed_not_in_source"
    assert result["source_scientific_reviewed"] is False
    assert result["semantic_scope_source_verified"] is False
    assert result["may_publish"] is False
    assert result["new_canonical_statement_created"] is False
    assert result == verify(deepcopy(proof), concepts, statements)


def test_rule_is_compositional_and_supports_three_hop_proofs():
    proof, concepts, statements = sample()
    concepts.append({"id": EXTRA, "label": "Extra", "slug": "extra"})
    statements.append({
        "id": CD,
        "subject": {"kind": "concept", "id": DATA},
        "predicate": "subtype_of",
        "object": {"kind": "concept", "id": EXTRA},
    })
    proof["steps"].insert(2, {
        "id": "h3", "rule": "recorded_subtype",
        "statement_id": CD, "assumed_scope": SCOPE,
    })
    proof["steps"].append({
        "id": "s2", "rule": "subtype_transitivity", "left": "s1", "right": "h3"
    })
    proof["conclusion_step_id"] = "s2"
    proof["goal"]["object_concept_id"] = EXTRA
    result = verify(proof, concepts, statements)
    assert result["original_recorded_premises"] == [AB, BC, CD]
    assert result["steps"][-1]["premise_step_ids"] == ["s1", "h3"]
    assert result["conclusion"]["object_label"] == "Extra"


@pytest.mark.parametrize("alter", [
    lambda p, c, s: p.update({"scope": "reviewed_scope"}),
    lambda p, c, s: p.update({"schema_version": "formal-scoped-subtype-proof.v2"}),
    lambda p, c, s: p["provenance"].update({"source_scientific_review": "verified"}),
    lambda p, c, s: p["provenance"].update({"scope_origin": "from_source"}),
    lambda p, c, s: p["steps"][0].update({"assumed_scope": "hypothetical_other"}),
    lambda p, c, s: p["steps"][0].update({"statement_id": "00000000-0000-4000-8000-000000000099"}),
    lambda p, c, s: p["steps"][1].update({"statement_id": AB}),
    lambda p, c, s: p["steps"][2].update({"left": "h2", "right": "h1"}),
    lambda p, c, s: p["steps"][2].update({"left": "s1"}),
    lambda p, c, s: p["steps"][2].update({"right": "future"}),
    lambda p, c, s: p["steps"][2].update({"rule": "subtype_symmetry"}),
    lambda p, c, s: p["steps"][1].update({"id": "h1"}),
    lambda p, c, s: p["steps"][0].update({"extra": "trusted"}),
    lambda p, c, s: p["goal"].update({"predicate": "uses"}),
    lambda p, c, s: p["goal"].update({"object_concept_id": ARRAY}),
    lambda p, c, s: p.update({"conclusion_step_id": "h1"}),
    lambda p, c, s: p.update({"conclusion_step_id": "bogus"}),
    lambda p, c, s: s[0].update({"predicate": "uses"}),
    lambda p, c, s: s[1].update({"subject": {"kind": "concept", "id": ARRAY}}),
    lambda p, c, s: s[1].update({"object": {"kind": "literal", "datatype": "string", "value": "data"}}),
])
def test_no_bad_rule_context_reference_or_premise_is_accepted(alter):
    proof, concepts, statements = sample()
    alter(proof, concepts, statements)
    with pytest.raises(ScopedSubtypeProofError):
        verify(proof, concepts, statements)


def test_snapshot_drift_detected_even_if_original_uuid_is_unchanged():
    proof, concepts, statements = sample()
    result = verify(proof, concepts, statements)
    original_concepts = rows_bytes(concepts)
    original_statements = rows_bytes(statements)
    tampered = rows_bytes([{**statements[0], "predicate": "uses"}, statements[1]])
    with pytest.raises(ScopedSubtypeProofError, match="snapshot mismatch"):
        verify_scoped_subtype_proof(
            proof, concepts_jsonl=original_concepts, statements_jsonl=tampered
        )
    assert "sha256" in result["proof_fingerprint"]
    assert result["source_snapshot"]["concepts_sha256"] == proof["snapshot"]["concepts_sha256"]
    assert rows_bytes(concepts) == original_concepts and rows_bytes(statements) == original_statements


def test_claim_from_non_subtype_record_is_rejected_regardless_of_hypothetical_scope():
    proof, concepts, statements = sample()
    statements[1]["predicate"] = "part_of"
    with pytest.raises(ScopedSubtypeProofError, match="different predicate"):
        verify(proof, concepts, statements)


def test_three_hypotheses_cannot_be_reordered_to_fake_a_chain():
    proof, concepts, statements = sample()
    proof["steps"][2]["left"], proof["steps"][2]["right"] = "h2", "h1"
    with pytest.raises(ScopedSubtypeProofError, match="requires left.target == right.subject"):
        verify(proof, concepts, statements)


def test_proof_scope_labels_are_not_accepted_as_reviewed_source_semantics():
    proof, concepts, statements = sample()
    proof["scope"] = "hypothetical_ambiguous"
    proof["steps"][0]["assumed_scope"] = "hypothetical_ambiguous"
    proof["steps"][1]["assumed_scope"] = "hypothetical_ambiguous"
    outcome = verify(proof, concepts, statements)
    assert outcome["semantic_scope_source_verified"] is False
    assert outcome["source_scientific_reviewed"] is False
