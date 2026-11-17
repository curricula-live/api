"""Generic, evidence-linked subtype path discovery without concept-specific code."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from uuid import UUID

import pytest

from core.formal_subtype_discovery import (
    ScopedSubtypeProofError,
    discover_scoped_subtype_certificate,
)
from core.formal_scoped_subtype_proofs import verify_scoped_subtype_proof

ARRAY = "ea8c3f31-8745-52b1-9e29-d5fcf6ab16ba"
COLLECTION = "c5c9fcca-3db2-56f9-bceb-ec4dabd6ee78"
DATA = "2bfccfc4-b578-5dad-a6b2-361106b178b0"
EXTRA = "00000000-0000-4000-8000-000000000004"
AB = "048adf33-0701-43de-998f-20c299388f51"
BC = "15ead31d-e970-4aad-a4f8-7c9fccf3097a"
CD = "00000000-0000-4000-8000-000000000008"
DIRECT = "00000000-0000-4000-8000-000000000009"


def _record(identifier, source, predicate, target):
    return {
        "id": identifier,
        "subject": {"kind": "concept", "id": source},
        "predicate": predicate,
        "object": {"kind": "concept", "id": target},
    }


def snapshot(*, more=False, direct=False):
    concepts = [
        {"id": ARRAY, "slug": "array", "label": "Array"},
        {"id": COLLECTION, "slug": "collection", "label": "Collection"},
        {"id": DATA, "slug": "data", "label": "Data"},
    ]
    statements = [
        _record(AB, ARRAY, "subtype_of", COLLECTION),
        _record(BC, COLLECTION, "subtype_of", DATA),
    ]
    if more:
        concepts.append({"id": EXTRA, "slug": "extra", "label": "Extra"})
        statements.append(_record(CD, DATA, "subtype_of", EXTRA))
    if direct:
        statements.append(_record(DIRECT, ARRAY, "subtype_of", DATA))
    return (
        b"".join(json.dumps(row, sort_keys=True).encode() + b"\n" for row in concepts),
        b"".join(json.dumps(row, sort_keys=True).encode() + b"\n" for row in statements),
    )


def discover(concepts, statements, start=ARRAY, target=DATA, **kw):
    return discover_scoped_subtype_certificate(
        concepts_jsonl=concepts,
        statements_jsonl=statements,
        subject_concept_id=start,
        object_concept_id=target,
        **kw,
    )


def checked(cert, concepts, statements):
    return verify_scoped_subtype_proof(
        cert, concepts_jsonl=concepts, statements_jsonl=statements
    )


def test_derivation_is_generated_and_independently_verified_from_original_relation_ids():
    concepts, statements = snapshot()
    certificate = discover(concepts, statements)
    assert certificate["goal"]["subject_concept_id"] == ARRAY
    assert certificate["goal"]["object_concept_id"] == DATA
    assert certificate["steps"] == [
        {"id": "h1", "rule": "recorded_subtype", "statement_id": AB,
         "assumed_scope": "hypothetical_shared_taxonomy"},
        {"id": "h2", "rule": "recorded_subtype", "statement_id": BC,
         "assumed_scope": "hypothetical_shared_taxonomy"},
        {"id": "s1", "rule": "subtype_transitivity", "left": "h1", "right": "h2"},
    ]
    proof = checked(certificate, concepts, statements)
    assert proof["original_recorded_premises"] == [AB, BC]
    assert proof["conclusion"]["object_label"] == "Data"
    assert proof["semantic_scope_source_verified"] is False
    assert proof["may_publish"] is False
    assert discover(concepts, statements) == deepcopy(certificate)


def test_generator_builds_three_hop_compositional_certificate():
    concepts, statements = snapshot(more=True)
    certificate = discover(concepts, statements, target=EXTRA)
    assert len(certificate["steps"]) == 5
    assert certificate["conclusion_step_id"] == "s2"
    assert certificate["steps"][-1] == {
        "id": "s2", "rule": "subtype_transitivity", "left": "s1", "right": "h3"
    }
    checked_proof = checked(certificate, concepts, statements)
    assert checked_proof["original_recorded_premises"] == [AB, BC, CD]


def test_direct_assertion_is_not_reinvented_without_an_alternate_path():
    concepts, statements = snapshot(direct=True)
    certificate = discover(concepts, statements)
    assert [step["statement_id"] for step in certificate["steps"] if step["rule"] == "recorded_subtype"] == [AB, BC]

    single_concepts, single_statements = snapshot()
    single_statements = b"".join(
        line + b"\n" for line in single_statements.splitlines()
        if b'"id": "15ead31d' not in line
    )
    with pytest.raises(ScopedSubtypeProofError, match="No two-or-more-edge"):
        discover(single_concepts, single_statements, start=ARRAY, target=COLLECTION)


def test_unused_uses_relation_is_not_treated_as_subtype():
    concepts, statements = snapshot()
    parsed = [json.loads(x) for x in statements.splitlines()]
    parsed[0]["predicate"] = "uses"
    rewritten = b"".join(json.dumps(x).encode() + b"\n" for x in parsed)
    with pytest.raises(ScopedSubtypeProofError, match="No two-or-more-edge"):
        discover(concepts, rewritten)


def test_reverse_and_missing_paths_do_not_invent_inverse_subtypes():
    concepts, statements = snapshot()
    with pytest.raises(ScopedSubtypeProofError, match="No two-or-more-edge"):
        discover(concepts, statements, start=DATA, target=ARRAY)
    with pytest.raises(ScopedSubtypeProofError, match="No two-or-more-edge"):
        discover(concepts, statements, start=COLLECTION, target=ARRAY)


def test_no_cycles_or_unbounded_search_and_hops():
    concepts, statements = snapshot(more=True)
    with pytest.raises(ScopedSubtypeProofError, match="No two-or-more-edge"):
        discover(concepts, statements, target=EXTRA, max_hops=2)
    with pytest.raises(ScopedSubtypeProofError, match="2–6"):
        discover(concepts, statements, max_hops=999)
    with pytest.raises(ScopedSubtypeProofError, match="Reflexive/cyclic"):
        discover(concepts, statements, start=ARRAY, target=ARRAY)


def test_scope_is_explicit_and_never_looked_up_as_certified_from_data():
    concepts, statements = snapshot()
    certificate = discover(concepts, statements, assumed_scope="hypothetical_math_taxonomy")
    assert all(
        step["assumed_scope"] == "hypothetical_math_taxonomy"
        for step in certificate["steps"] if step["rule"] == "recorded_subtype"
    )
    result = checked(certificate, concepts, statements)
    assert result["semantic_scope_source_verified"] is False
    assert result["scope_origin"] == "assumed_not_in_source"
    with pytest.raises(ScopedSubtypeProofError, match="hypothetical"):
        discover(concepts, statements, assumed_scope="reviewed_science")


def test_unknown_concepts_and_duplicate_canonical_uuid_fail():
    concepts, statements = snapshot()
    with pytest.raises((ScopedSubtypeProofError, ValueError)):
        discover(concepts, statements, target="00000000-0000-4000-8000-000000000099")
    with pytest.raises(ScopedSubtypeProofError, match="duplicated concept"):
        discover(concepts + concepts.splitlines()[0] + b"\n", statements)


def test_certificate_invalidated_after_source_mutation():
    concepts, statements = snapshot()
    certificate = discover(concepts, statements)
    changed = statements.replace(b"subtype_of", b"part_of", 1)
    assert changed != statements
    with pytest.raises(ScopedSubtypeProofError, match="snapshot mismatch"):
        checked(certificate, concepts, changed)
