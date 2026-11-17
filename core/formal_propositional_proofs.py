"""Strict synthetic propositional proof checker; no canonical data or HTTP.

This verifies natural-deduction steps and tracks undischarged assumptions.
It does NOT establish the scientific truth of atoms, authenticate ontology
statements, or make any proof available to the public website.

Rules: assume, and_intro, and_elim_left/right, imp_elim, imp_intro,
or_intro_left/right, iff_elim_left/right. Negation and bottom/top are
supported as formula SYNTAX but have no introduction/elimination rules yet.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from itertools import product
import json
import re
from typing import Mapping

VERSION = "formal-propositional-proof.v0"
MAX_STEPS = 96
MAX_FORMULA_DEPTH = 12
MAX_FORMULA_NODES = 128
ATOM = re.compile(r"^[A-Z][A-Za-z0-9_]{0,31}$")
IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
SCOPE = re.compile(r"^[a-z][a-z0-9_-]{0,79}$")


class PropositionalProofError(ValueError):
    """Malformed or unjustified proof."""


@dataclass(frozen=True)
class VerifiedStep:
    formula: dict
    assumptions: frozenset[str]
    rule: str


def _require_fields(value: object, required: set[str], context: str) -> dict:
    if not isinstance(value, dict) or set(value) != required:
        raise PropositionalProofError(
            f"{context}: expected exactly {sorted(required)}"
        )
    return value


def _check_formula(formula: object, *, context: str) -> int:
    count = 0

    def walk(node: object, depth: int) -> None:
        nonlocal count
        if depth > MAX_FORMULA_DEPTH:
            raise PropositionalProofError(f"{context}: formula exceeds depth limit")
        count += 1
        if count > MAX_FORMULA_NODES:
            raise PropositionalProofError(f"{context}: formula exceeds node limit")
        if not isinstance(node, dict):
            raise PropositionalProofError(f"{context}: expected formula object")
        op = node.get("op")
        if op == "atom":
            _require_fields(node, {"op", "name"}, context)
            if not isinstance(node["name"], str) or not ATOM.fullmatch(node["name"]):
                raise PropositionalProofError(f"{context}: invalid propositional atom")
        elif op in ("top", "bottom"):
            _require_fields(node, {"op"}, context)
        elif op == "not":
            _require_fields(node, {"op", "arg"}, context)
            walk(node["arg"], depth + 1)
        elif op in ("and", "or", "implies", "iff"):
            _require_fields(node, {"op", "left", "right"}, context)
            walk(node["left"], depth + 1)
            walk(node["right"], depth + 1)
        else:
            raise PropositionalProofError(f"{context}: unsupported formula operator")

    walk(formula, 1)
    return count


_PRIORITY = {
    "iff": 1, "implies": 2, "or": 3,
    "and": 4, "not": 5, "atom": 6, "top": 6, "bottom": 6,
}
_OPERATORS = {
    "and": ("∧", r"\land", "and"),
    "or": ("∨", r"\lor", "or"),
    "implies": ("⇒", r"\Rightarrow", "implies"),
    "iff": ("⇔", r"\Leftrightarrow", "if and only if"),
}


def render_formula(formula: dict) -> dict[str, str]:
    """Return three representations of a validated formula; no raw LaTeX."""
    _check_formula(formula, context="render")

    def visit(node: dict) -> tuple[str, str, str]:
        op = node["op"]
        if op == "atom":
            name = node["name"]
            return name, r"\mathsf{" + name.replace("_", r"\_") + "}", name
        if op == "top":
            return "⊤", r"\top", "true"
        if op == "bottom":
            return "⊥", r"\bot", "false"
        if op == "not":
            u, l, p = visit(node["arg"])
            if _PRIORITY[node["arg"]["op"]] < _PRIORITY[op]:
                return f"¬({u})", r"\neg\left(" + l + r"\right)", f"not ({p})"
            return "¬" + u, r"\neg " + l, "not " + p

        left, right = node["left"], node["right"]
        left_text = visit(left)
        right_text = visit(right)
        priority = _PRIORITY[op]

        def wrap(child: dict, text: tuple[str, str, str], *, left_side: bool):
            child_priority = _PRIORITY[child["op"]]
            needs_parens = (
                child_priority < priority
                or (
                    child_priority == priority
                    and op in ("iff", "implies")
                )
            )
            if not needs_parens:
                return text
            return (
                "(" + text[0] + ")",
                r"\left(" + text[1] + r"\right)",
                "(" + text[2] + ")",
            )

        lparts = wrap(left, left_text, left_side=True)
        rparts = wrap(right, right_text, left_side=False)
        symbol, latex_op, plain_op = _OPERATORS[op]
        return (
            lparts[0] + f" {symbol} " + rparts[0],
            lparts[1] + " " + latex_op + " " + rparts[1],
            lparts[2] + " " + plain_op + " " + rparts[2],
        )

    unicode, latex, text = visit(formula)
    return {"unicode": unicode, "latex": latex, "mechanical_text": text}


_RULE_FIELDS: dict[str, set[str]] = {
    "assume": {"formula"},
    "and_intro": {"left", "right"},
    "and_elim_left": {"conjunction"},
    "and_elim_right": {"conjunction"},
    "imp_elim": {"implication", "antecedent"},
    "imp_intro": {"assumption", "conclusion"},
    "or_intro_left": {"premise", "other"},
    "or_intro_right": {"premise", "other"},
    "iff_elim_left": {"equivalence"},
    "iff_elim_right": {"equivalence"},
    "iff_intro": {"left", "right"},
}


def _atoms(formula: dict, result: set[str]) -> None:
    op = formula["op"]
    if op == "atom":
        result.add(formula["name"])
    elif op == "not":
        _atoms(formula["arg"], result)
    elif op in _OPERATORS:
        _atoms(formula["left"], result)
        _atoms(formula["right"], result)


def _evaluate(formula: dict, assignment: Mapping[str, bool]) -> bool:
    op = formula["op"]
    if op == "atom":
        return assignment[formula["name"]]
    if op == "top":
        return True
    if op == "bottom":
        return False
    if op == "not":
        return not _evaluate(formula["arg"], assignment)
    left = _evaluate(formula["left"], assignment)
    right = _evaluate(formula["right"], assignment)
    if op == "and":
        return left and right
    if op == "or":
        return left or right
    if op == "implies":
        return (not left) or right
    if op == "iff":
        return left == right
    raise PropositionalProofError("Unknown truth-value operator")


def verify_propositional_proof(proof: dict) -> dict:
    """Check every rule, exact premise dependency and assumption context.

    If undischarged assumptions remain, returns a CONDITIONAL result. A
    closed proof is a syntactic theorem in this experimental calculus, not a
    verification of any external assertion. For <=8 atoms an independent
    truth table checks the resulting semantic entailment.
    """
    _require_fields(
        proof,
        {
            "schema_version", "scope", "provenance", "goal",
            "steps", "conclusion_step_id",
        },
        "proof",
    )
    if proof["schema_version"] != VERSION:
        raise PropositionalProofError("Unsupported propositional proof version")
    if not isinstance(proof["scope"], str) or not SCOPE.fullmatch(proof["scope"]):
        raise PropositionalProofError("Invalid scope")
    _require_fields(proof["provenance"], {"status"}, "provenance")
    if proof["provenance"]["status"] != "synthetic_fixture":
        raise PropositionalProofError("Only synthetic fixtures may be checked")
    _check_formula(proof["goal"], context="goal")
    steps = proof["steps"]
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
        raise PropositionalProofError("Invalid proof step count")
    declared_goal = proof["conclusion_step_id"]
    if not isinstance(declared_goal, str) or not IDENTIFIER.fullmatch(declared_goal):
        raise PropositionalProofError("Invalid conclusion step identifier")

    checked: dict[str, VerifiedStep] = {}
    trace: list[dict] = []

    def earlier(identifier: object, *, source: str) -> VerifiedStep:
        if not isinstance(identifier, str) or identifier not in checked:
            raise PropositionalProofError(f"{source}: missing or forward-referenced step")
        return checked[identifier]

    for step in steps:
        if not isinstance(step, dict):
            raise PropositionalProofError("Expected proof step object")
        rule, identifier = step.get("rule"), step.get("id")
        if rule not in _RULE_FIELDS:
            raise PropositionalProofError("Unknown proof rule")
        if not isinstance(identifier, str) or not IDENTIFIER.fullmatch(identifier):
            raise PropositionalProofError("Invalid step identifier")
        if identifier in checked:
            raise PropositionalProofError(f"Duplicate step identifier: {identifier}")
        _require_fields(step, {"id", "rule"} | _RULE_FIELDS[rule], f"{identifier}/{rule}")

        parents: list[str] = []
        if rule == "assume":
            _check_formula(step["formula"], context=identifier)
            result = VerifiedStep(step["formula"], frozenset({identifier}), rule)

        elif rule == "and_intro":
            l, r = earlier(step["left"], source=identifier), earlier(step["right"], source=identifier)
            parents = [step["left"], step["right"]]
            result = VerifiedStep(
                {"op": "and", "left": l.formula, "right": r.formula},
                l.assumptions | r.assumptions, rule,
            )

        elif rule in ("and_elim_left", "and_elim_right"):
            premise = earlier(step["conjunction"], source=identifier)
            parents = [step["conjunction"]]
            if premise.formula["op"] != "and":
                raise PropositionalProofError(f"{identifier}: cannot eliminate non-conjunction")
            field = "left" if rule.endswith("left") else "right"
            result = VerifiedStep(premise.formula[field], premise.assumptions, rule)

        elif rule == "iff_intro":
            forward = earlier(step["left"], source=identifier)
            backward = earlier(step["right"], source=identifier)
            parents = [step["left"], step["right"]]
            if (
                forward.formula["op"] != "implies"
                or backward.formula["op"] != "implies"
                or forward.formula["left"] != backward.formula["right"]
                or forward.formula["right"] != backward.formula["left"]
            ):
                raise PropositionalProofError(
                    f"{identifier}: iff introduction requires two opposite implications"
                )
            result = VerifiedStep(
                {"op": "iff",
                 "left": forward.formula["left"],
                 "right": forward.formula["right"]},
                forward.assumptions | backward.assumptions,
                rule,
            )

        elif rule == "imp_elim":
            implication = earlier(step["implication"], source=identifier)
            antecedent = earlier(step["antecedent"], source=identifier)
            parents = [step["implication"], step["antecedent"]]
            if implication.formula["op"] != "implies" or implication.formula["left"] != antecedent.formula:
                raise PropositionalProofError(
                    f"{identifier}: modus ponens requires matching antecedent and implication"
                )
            result = VerifiedStep(
                implication.formula["right"],
                implication.assumptions | antecedent.assumptions, rule,
            )

        elif rule == "imp_intro":
            assumption = earlier(step["assumption"], source=identifier)
            conclusion = earlier(step["conclusion"], source=identifier)
            parents = [step["assumption"], step["conclusion"]]
            if assumption.rule != "assume":
                raise PropositionalProofError(f"{identifier}: discharge must reference an assumption step")
            result = VerifiedStep(
                {"op": "implies", "left": assumption.formula, "right": conclusion.formula},
                conclusion.assumptions - {step["assumption"]},
                rule,
            )

        elif rule in ("or_intro_left", "or_intro_right"):
            premise = earlier(step["premise"], source=identifier)
            _check_formula(step["other"], context=identifier)
            parents = [step["premise"]]
            l, r = ((premise.formula, step["other"]) if rule.endswith("left")
                    else (step["other"], premise.formula))
            result = VerifiedStep(
                {"op": "or", "left": l, "right": r}, premise.assumptions, rule,
            )

        else:
            equivalence = earlier(step["equivalence"], source=identifier)
            parents = [step["equivalence"]]
            if equivalence.formula["op"] != "iff":
                raise PropositionalProofError(f"{identifier}: requires an equivalence premise")
            l, r = equivalence.formula["left"], equivalence.formula["right"]
            if rule == "iff_elim_right":
                l, r = r, l
            result = VerifiedStep(
                {"op": "implies", "left": l, "right": r},
                equivalence.assumptions, rule,
            )

        _check_formula(result.formula, context=identifier)
        checked[identifier] = result
        trace.append({
            "id": identifier,
            "rule": rule,
            "formula": result.formula,
            **render_formula(result.formula),
            "premise_step_ids": parents,
            "open_assumption_step_ids": sorted(result.assumptions),
            "discharged_assumption_step_id": step["assumption"] if rule == "imp_intro" else None,
        })

    if declared_goal not in checked:
        raise PropositionalProofError("Conclusion step does not exist")
    final = checked[declared_goal]
    if final.formula != proof["goal"]:
        raise PropositionalProofError("Claimed goal does not match the computed conclusion")

    assumptions = sorted(final.assumptions)
    atom_names: set[str] = set()
    _atoms(final.formula, atom_names)
    for item in assumptions:
        _atoms(checked[item].formula, atom_names)
    assignment_count = 0
    if len(atom_names) <= 8:
        names = sorted(atom_names)
        for values in product((False, True), repeat=len(names)):
            assignment = dict(zip(names, values))
            assignment_count += 1
            if (
                all(_evaluate(checked[key].formula, assignment) for key in assumptions)
                and not _evaluate(final.formula, assignment)
            ):
                raise PropositionalProofError(
                    "Semantic counterexample: final goal does not follow from open assumptions"
                )

    fingerprint = "sha256:" + sha256(
        json.dumps(proof, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()

    return {
        "schema_version": VERSION,
        "proof_fingerprint": fingerprint,
        "scope": proof["scope"],
        "status": "synthetic_proof_checked",
        "theorem_in_experimental_calculus": len(assumptions) == 0,
        "open_assumption_step_ids": assumptions,
        "conclusion": render_formula(final.formula),
        "conclusion_step_id": declared_goal,
        "steps": trace,
        "semantic_truth_table_checked": len(atom_names) <= 8,
        "truth_table_assignments": assignment_count,
        "logical_rules_checked": True,
        "scientific_sources_verified": False,
        "canonical_claim_approved": False,
        "may_publish": False,
    }


def main() -> None:
    """Inspect a synthetic proof without requiring Django or a database."""
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("certificate", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    certificate = json.loads(args.certificate.read_text(encoding="utf-8"))
    verified = verify_propositional_proof(certificate)
    if args.format == "json":
        print(json.dumps(verified, indent=2, ensure_ascii=False))
        return
    print("Formal propositional proof · SYNTHETIC")
    print("Goal:", verified["conclusion"]["unicode"])
    print("Scope:", verified["scope"])
    for step in verified["steps"]:
        deps = ", ".join(step["premise_step_ids"]) or "assumption"
        open_ids = ",".join(step["open_assumption_step_ids"]) or "∅"
        discharged = (
            f" · discharge {step['discharged_assumption_step_id']}"
            if step["discharged_assumption_step_id"] else ""
        )
        print(
            f"{step['id']:>4}  {step['unicode']:<42}"
            f"[{step['rule']}: {deps}{discharged}]  Γ={{{open_ids}}}"
        )
    label = "closed synthetic theorem" if verified["theorem_in_experimental_calculus"] else "conditional consequence"
    print("Result:", label)
    print("Truth table valuations checked:", verified["truth_table_assignments"])
    print("Canonical/scientific claim approved:", verified["canonical_claim_approved"])


if __name__ == "__main__":
    main()
