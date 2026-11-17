"""Conditional class equivalence from TWO independently checked scoped subtype proofs.

A ⊑ B together with B ⊑ A entails class equivalence A ≡ B within
one interpretation. This module never reconstructs a semantic scope from
legacy canonical data; the shared scope here is a synthetic hypothesis.

It is deliberately different from propositional iff-introduction:
  (P ⇒ Q) & (Q ⇒ P) -> P ⇔ Q   [propositional]
  A ⊑ B & B ⊑ A       -> A ≡ B [class equivalence]
"""
from __future__ import annotations

from hashlib import sha256
import json

from core.formal_scoped_subtype_proofs import (
    ScopedSubtypeProofError, verify_scoped_subtype_proof,
)
from core.formal_class_models import _latex_label


class ConditionalEquivalenceError(ValueError):
    pass


def verify_mutual_subsumption(
    forward_certificate: dict,
    reverse_certificate: dict,
    *,
    concepts_jsonl: bytes,
    statements_jsonl: bytes,
) -> dict:
    try:
        forward = verify_scoped_subtype_proof(
            forward_certificate,
            concepts_jsonl=concepts_jsonl,
            statements_jsonl=statements_jsonl,
        )
        backward = verify_scoped_subtype_proof(
            reverse_certificate,
            concepts_jsonl=concepts_jsonl,
            statements_jsonl=statements_jsonl,
        )
    except ScopedSubtypeProofError as exc:
        raise ConditionalEquivalenceError(f"Invalid constituent subsumption proof: {exc}") from exc

    if forward["scope"] != backward["scope"]:
        raise ConditionalEquivalenceError("Both directions must have identical scope")
    if forward["source_snapshot"] != backward["source_snapshot"]:
        raise ConditionalEquivalenceError("Both directions must have the exact same pinned snapshot")
    if forward["scope_origin"] != "assumed_not_in_source" or backward["scope_origin"] != "assumed_not_in_source":
        raise ConditionalEquivalenceError("Cannot claim that legacy source provided a reviewed scope")
    left = forward["conclusion"]
    right = backward["conclusion"]
    a, b = left["subject_concept_id"], left["object_concept_id"]
    if a == b:
        raise ConditionalEquivalenceError("Reflexive class equivalence is not this rule's goal")
    if (right["subject_concept_id"], right["object_concept_id"]) != (b, a):
        raise ConditionalEquivalenceError("Reverse proof must establish B ⊑ A for the exact same A, B")
    if left["predicate"] != "subtype_of" or right["predicate"] != "subtype_of":
        raise ConditionalEquivalenceError("Only class subsumption proofs can establish this rule")
    if not forward["proof_steps_checked"] or not backward["proof_steps_checked"]:
        raise ConditionalEquivalenceError("Both direction proofs must be checked")

    original_ids = list(dict.fromkeys(
        forward["original_recorded_premises"] + backward["original_recorded_premises"]
    ))
    fingerprint = "sha256:" + sha256(json.dumps(
        {
            "forward": forward["proof_fingerprint"],
            "reverse": backward["proof_fingerprint"],
            "scope": forward["scope"],
        }, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    return {
        "schema_version": "formal-mutual-subsumption.v0",
        "rule_id": "mutual_subsumption@v0",
        "scope": forward["scope"],
        "scope_origin": "assumed_not_in_source",
        "class_equivalence": {
            "left_concept_id": a,
            "left_label": left["subject_label"],
            "operator": "≡",
            "right_concept_id": b,
            "right_label": left["object_label"],
            "unicode": f"{left['subject_label']} ≡ {left['object_label']}",
            "latex": _latex_label(left["subject_label"]) + r" \equiv " +
                     _latex_label(left["object_label"]),
            "status": "conditional_on_both_directions_and_hypothetical_scope",
        },
        "directional_witnesses": [
            {
                "direction": "forward",
                "rule_id": forward["rule_id"],
                "proof_fingerprint": forward["proof_fingerprint"],
                "conclusion": left,
                "original_statement_ids": forward["original_recorded_premises"],
            },
            {
                "direction": "backward",
                "rule_id": backward["rule_id"],
                "proof_fingerprint": backward["proof_fingerprint"],
                "conclusion": right,
                "original_statement_ids": backward["original_recorded_premises"],
            },
        ],
        "original_statement_ids": original_ids,
        "proof_fingerprint": fingerprint,
        "both_directions_checked": True,
        "source_semantics_verified": False,
        "new_canonical_statement_created": False,
        "may_publish": False,
    }
