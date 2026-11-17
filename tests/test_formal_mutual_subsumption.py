"""Class equivalence requires both independently verified directions and a common scope."""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from core.formal_subtype_discovery import discover_scoped_subtype_certificate
from core.formal_mutual_subsumption import (
    ConditionalEquivalenceError, verify_mutual_subsumption,
)

A = "00000000-0000-4000-8000-000000000001"
B = "00000000-0000-4000-8000-000000000002"
C = "00000000-0000-4000-8000-000000000003"
D = "00000000-0000-4000-8000-000000000004"


def _jsonl(rows):
    return b"".join(json.dumps(row, sort_keys=True).encode() + b"\n" for row in rows)


def _edge(idx, a, b, predicate="subtype_of"):
    return {
        "id": f"00000000-0000-4000-8000-00000000001{idx}",
        "subject": {"kind": "concept", "id": a},
        "predicate": predicate,
        "object": {"kind": "concept", "id": b},
    }


def sample():
    concepts = _jsonl([
        {"id": A, "label": "Class A", "slug": "class-a"},
        {"id": B, "label": "Class B", "slug": "class-b"},
        {"id": C, "label": "Intermediate C", "slug": "intermediate-c"},
        {"id": D, "label": "Intermediate D", "slug": "intermediate-d"},
    ])
    statements = _jsonl([
        _edge(1, A, C),
        _edge(2, C, B),
        _edge(3, B, D),
        _edge(4, D, A),
    ])
    forward = discover_scoped_subtype_certificate(
        concepts_jsonl=concepts, statements_jsonl=statements,
        subject_concept_id=A, object_concept_id=B,
        assumed_scope="hypothetical_shared_taxonomy",
    )
    reverse = discover_scoped_subtype_certificate(
        concepts_jsonl=concepts, statements_jsonl=statements,
        subject_concept_id=B, object_concept_id=A,
        assumed_scope="hypothetical_shared_taxonomy",
    )
    return forward, reverse, concepts, statements


def verify(forward, reverse, concepts, statements):
    return verify_mutual_subsumption(
        forward, reverse,
        concepts_jsonl=concepts, statements_jsonl=statements,
    )


def test_two_directional_proofs_can_produce_only_conditional_class_equivalence():
    forward, reverse, concepts, statements = sample()
    result = verify(forward, reverse, concepts, statements)
    equivalence = result["class_equivalence"]
    assert equivalence["unicode"] == "Class A ≡ Class B"
    assert equivalence["operator"] == "≡"
    assert r"\equiv" in equivalence["latex"]
    assert result["both_directions_checked"] is True
    assert result["scope"] == "hypothetical_shared_taxonomy"
    assert result["source_semantics_verified"] is False
    assert result["may_publish"] is False
    assert result["new_canonical_statement_created"] is False
    assert [w["direction"] for w in result["directional_witnesses"]] == [
        "forward", "backward"
    ]
    assert len(result["original_statement_ids"]) == 4
    assert result == verify(deepcopy(forward), deepcopy(reverse), concepts, statements)


def test_one_direction_alone_is_not_an_equivalence():
    forward, reverse, concepts, statements = sample()
    with pytest.raises(ConditionalEquivalenceError, match="Reverse proof"):
        verify(forward, forward, concepts, statements)
    with pytest.raises(ConditionalEquivalenceError):
        verify(forward, {}, concepts, statements)


def test_equivalence_requires_shared_scope_not_arbitrary_labels():
    forward, reverse, concepts, statements = sample()
    reverse["scope"] = "hypothetical_different_taxonomy"
    for step in reverse["steps"]:
        if step["rule"] == "recorded_subtype":
            step["assumed_scope"] = reverse["scope"]
    with pytest.raises(ConditionalEquivalenceError, match="identical scope"):
        verify(forward, reverse, concepts, statements)


def test_wrong_direction_is_not_an_equivalence():
    forward, reverse, concepts, statements = sample()
    backward = deepcopy(reverse)
    backward["goal"]["object_concept_id"] = B
    with pytest.raises(ConditionalEquivalenceError):
        verify(forward, backward, concepts, statements)


def test_tampered_source_invalidates_both_certificates():
    forward, reverse, concepts, statements = sample()
    modified = statements.replace(b"subtype_of", b"uses", 1)
    with pytest.raises(ConditionalEquivalenceError, match="snapshot mismatch"):
        verify(forward, reverse, concepts, modified)


def test_bad_predicate_cannot_be_used_for_one_direction():
    # Syntactically symmetric IDs do not make an arbitrary relation a class subsumption.
    forward, reverse, concepts, statements = sample()
    modified = statements.replace(b"subtype_of", b"uses", 1)
    with pytest.raises(ConditionalEquivalenceError):
        verify(forward, reverse, concepts, modified)


def test_proof_context_origin_is_not_accepted_as_certified_from_source():
    forward, reverse, concepts, statements = sample()
    reverse["provenance"]["scope_origin"] = "source_verified"
    with pytest.raises(ConditionalEquivalenceError):
        verify(forward, reverse, concepts, statements)
