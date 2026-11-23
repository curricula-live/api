"""Typed, source-linked expression projections for the legacy teacher Overview.

Class expressions and propositional formulas are distinct syntactic sorts.
Only recorded subtype-of assertions and checked, conditional subtype traces
are eligible; inverse, negated, disjunctive, quantified and biconditional
conclusions are never invented from absence or lexical similarity.
"""
from __future__ import annotations


def direct_class_conditions(slug: str, edges: list[dict]) -> dict | None:
    """Conjoin independent *necessary* superclass conditions, never equivalence."""
    direct = sorted(
        (edge for edge in edges
         if edge["source"] == slug and edge["predicate"] == "subtype_of"
         and edge["target"] != slug),
        key=lambda e: (e["target"], e["id"]),
    )
    unique: list[dict] = []
    seen: set[str] = set()
    for edge in direct:
        if edge["target"] not in seen:
            seen.add(edge["target"])
            unique.append(edge)
        if len(unique) == 4:
            break
    if len(unique) < 2:
        return None

    return {
        "kind": "necessary_class_condition",
        "expression": {
            "op": "subsumption",
            "left": {"op": "concept", "slug": slug},
            "right": {
                "op": "intersection",
                "args": [{"op": "concept", "slug": e["target"]} for e in unique],
            },
        },
        "assertion_ids": [e["id"] for e in unique],
        "status": "conditional_on_recorded_assertions",
        "source_semantics_verified": False,
        "equivalence_established": False,
        "may_publish": False,
        "scope_origin": "assumed_not_in_source",
    }


def transitivity_formula(derived: dict) -> dict:
    """A rule application as (premise1 AND premise2 AND ...) IMPLIES conclusion."""
    proof = derived["proof"]
    premises = [s for s in proof["steps"] if s["kind"] == "recorded_premise"]
    if len(premises) < 2 or [s["assertion_id"] for s in premises] != derived["premise_ids"]:
        raise ValueError("Cannot express an inference with a mismatched proof witness")
    if not proof["rule_application_checked"] or proof["source_semantics_verified"]:
        raise ValueError("Expected a checked, provisional proof trace")
    conclusion = next(
        (s for s in proof["steps"] if s["id"] == proof["conclusion_step_id"]),
        None,
    )
    if conclusion is None or (
        conclusion["subject"], conclusion["target"], conclusion["predicate"]
    ) != (derived["subject"], derived["target"], "subtype_of"):
        raise ValueError("Inference conclusion does not match checked proof")

    def as_subsumption(step: dict) -> dict:
        return {
            "op": "subsumption",
            "left": {"op": "concept", "slug": step["subject"]},
            "right": {"op": "concept", "slug": step["target"]},
        }

    return {
        "kind": "conditional_rule_formula",
        "expression": {
            "op": "implies",
            "left": {
                "op": "and",
                "args": [as_subsumption(p) for p in premises],
            },
            "right": as_subsumption(conclusion),
        },
        "assertion_ids": list(derived["premise_ids"]),
        "rule": "subtype_of_transitivity",
        "status": "conditional_on_recorded_assertions",
        "source_semantics_verified": False,
        "equivalence_established": False,
        "may_publish": False,
        "scope_origin": "assumed_not_in_source",
    }
