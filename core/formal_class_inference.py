"""Tiny proof-witnessed class-expression rule experiment (synthetic only).

No source assertions are admitted and no generic `uses` relationship is
promoted to a stronger scientific property. This module deliberately implements
only a sound **syntactic** rule: if S ⊑ (A ⊓ B), infer S ⊑ A and S ⊑ B.
For S ≡ (A ⊓ B), first obtain the left-to-right inclusion.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Mapping

from core.formal_class_models import render_formal_class_model


def derive_conjunction_consequences(
    model: dict,
    *,
    concept_labels: Mapping[str, str],
    predicate_labels: Mapping[str, str],
    known_statement_ids: set[str] | None = None,
) -> dict:
    base = render_formal_class_model(
        model,
        concept_labels=concept_labels,
        predicate_labels=predicate_labels,
        known_statement_ids=known_statement_ids,
    )
    fingerprint = "sha256:" + sha256(
        json.dumps(model, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()

    # An `or` node never licenses selecting one disjunct. A `some` role
    # restriction does not imply the subject is an instance of its filler.
    if model["expression"]["op"] != "and":
        return {
            "model_fingerprint": fingerprint,
            "applied_rules": [],
            "consequences": [],
            "status": "synthetic_conditional_only",
            "may_publish": False,
        }

    conclusions = []
    seen = set()

    def walk(expr: dict, selection: tuple[int, ...]) -> None:
        if expr["op"] == "and":
            for index, child in enumerate(expr["args"]):
                walk(child, (*selection, index))
            return

        candidate = {
            **model,
            "relation": "necessary",
            "expression": expr,
        }
        projected = render_formal_class_model(
            candidate,
            concept_labels=concept_labels,
            predicate_labels=predicate_labels,
            known_statement_ids=known_statement_ids,
        )
        if projected["unicode"] in seen:
            return
        seen.add(projected["unicode"])
        steps = []
        if model["relation"] == "equivalent":
            steps.append({"rule": "equivalence_to_subsumption"})
        steps.extend(
            {"rule": "right_intersection_elimination", "argument_index": index}
            for index in selection
        )
        conclusions.append({
            "unicode": projected["unicode"],
            "latex": projected["latex"],
            "mechanical_text": projected["mechanical_text"],
            "premise_model": fingerprint,
            "proof_steps": steps,
            "rule": "right_intersection_elimination",
            "status": "conditional_on_synthetic_axiom",
            "scientific_claim_verified": False,
            "may_publish": False,
        })

    walk(model["expression"], ())
    return {
        "model_fingerprint": fingerprint,
        "applied_rules": sorted({s["rule"] for c in conclusions for s in c["proof_steps"]}),
        "consequences": conclusions,
        "status": "synthetic_conditional_only",
        "may_publish": False,
    }
