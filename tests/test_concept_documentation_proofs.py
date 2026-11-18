"""Typed, provisional graph proof witnesses in the teacher documentation API."""
from __future__ import annotations

from copy import deepcopy
import uuid

import pytest

from core.concept_documentation_proofs import ProvisionalProofError, checked_subtype_trace


def edge(subject, target, predicate="subtype_of", identifier=None):
    return {
        "id": identifier or str(uuid.uuid4()), "source": subject,
        "target": target, "predicate": predicate,
    }


def test_exact_two_hop_proof_steps_and_unreviewed_semantics():
    first, second = edge("array", "collection"), edge("collection", "data")
    result = checked_subtype_trace("array", "data", [first["id"], second["id"]], [first, second])
    assert result["format"] == "provisional-subtype-trace@1"
    assert result["steps"] == [
        {
            "id": "h1", "kind": "recorded_premise", "rule": "recorded_subtype",
            "subject": "array", "predicate": "subtype_of", "target": "collection",
            "assertion_id": first["id"], "depends_on": [],
        },
        {
            "id": "h2", "kind": "recorded_premise", "rule": "recorded_subtype",
            "subject": "collection", "predicate": "subtype_of", "target": "data",
            "assertion_id": second["id"], "depends_on": [],
        },
        {
            "id": "s1", "kind": "derived_step", "rule": "subtype_of_transitivity",
            "subject": "array", "predicate": "subtype_of", "target": "data",
            "assertion_id": None, "depends_on": ["h1", "h2"],
        },
    ]
    assert result["conclusion_step_id"] == "s1"
    assert result["rule_application_checked"] is True
    assert result["scope_origin"] == "assumed_not_in_source"
    assert result["source_semantics_verified"] is False
    assert result["is_formal_proof_certificate"] is False
    assert result["may_publish"] is False


def test_three_hop_proof_contains_explicit_intermediate_step():
    a, b, c = edge("array", "collection"), edge("collection", "data"), edge("data", "value")
    result = checked_subtype_trace("array", "value", [a["id"], b["id"], c["id"]], [a, b, c])
    assert [step["id"] for step in result["steps"]] == ["h1", "h2", "h3", "s1", "s2"]
    assert result["steps"][-1]["depends_on"] == ["s1", "h3"]
    assert result["steps"][-1]["target"] == "value"


@pytest.mark.parametrize("mutate", [
    lambda a, b, p: p.reverse(),
    lambda a, b, p: p.append("unknown-uuid"),
    lambda a, b, p: p.pop(),
    lambda a, b, p: p.append(p[0]),
    lambda a, b, p: b.update({"predicate": "uses"}),
    lambda a, b, p: a.update({"predicate": "part_of"}),
    lambda a, b, p: b.update({"source": "wrong-middle"}),
    lambda a, b, p: b.update({"target": "collection"}),
])
def test_invalid_proof_witness_is_rejected(mutate):
    first, second = edge("array", "collection"), edge("collection", "data")
    path = [first["id"], second["id"]]
    mutate(first, second, path)
    with pytest.raises(ProvisionalProofError):
        checked_subtype_trace("array", "data", path, [first, second])


def test_no_phantom_graph_facts_are_added_to_assertion_list():
    a, b = edge("array", "collection"), edge("collection", "data")
    originals = deepcopy([a, b])
    proof = checked_subtype_trace("array", "data", [a["id"], b["id"]], [a, b])
    assert [a, b] == originals
    assert proof["steps"][-1]["assertion_id"] is None
