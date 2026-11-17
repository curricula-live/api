"""Fail-closed soundness and proof-context checks for synthetic propositions."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from core.formal_propositional_proofs import (
    MAX_FORMULA_DEPTH,
    PropositionalProofError,
    render_formula,
    verify_propositional_proof,
)

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "propositional-deduction.synthetic.json"


def sample():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def atom(name):
    return {"op": "atom", "name": name}


def implies(a, b):
    return {"op": "implies", "left": a, "right": b}


def proof(steps, goal, conclusion):
    return {
        "schema_version": "formal-propositional-proof.v0",
        "scope": "synthetic_propositional",
        "provenance": {"status": "synthetic_fixture"},
        "goal": goal,
        "steps": steps,
        "conclusion_step_id": conclusion,
    }


def test_closed_nested_implication_is_verified_and_all_hypotheses_discharged():
    report = verify_propositional_proof(sample())
    assert report["theorem_in_experimental_calculus"] is True
    assert report["open_assumption_step_ids"] == []
    assert report["semantic_truth_table_checked"] is True
    assert report["truth_table_assignments"] == 4
    assert report["conclusion"]["unicode"] == "P ⇒ ((P ⇒ Q) ⇒ Q)"
    assert report["steps"][2]["open_assumption_step_ids"] == ["h1", "h2"]
    assert report["steps"][3]["open_assumption_step_ids"] == ["h1"]
    assert report["steps"][4]["open_assumption_step_ids"] == []
    assert report["steps"][4]["discharged_assumption_step_id"] == "h1"
    assert report["status"] == "synthetic_proof_checked"
    assert report["may_publish"] is False
    assert report["scientific_sources_verified"] is False
    assert report["logical_rules_checked"] is True
    assert report["proof_fingerprint"] == verify_propositional_proof(deepcopy(sample()))["proof_fingerprint"]


def test_two_unclosed_assumptions_produce_conditional_entailment_not_theorem():
    P, Q = atom("P"), atom("Q")
    proof_obj = proof([
        {"id": "h1", "rule": "assume", "formula": P},
        {"id": "h2", "rule": "assume", "formula": implies(P, Q)},
        {"id": "s1", "rule": "imp_elim", "implication": "h2", "antecedent": "h1"},
    ], Q, "s1")
    result = verify_propositional_proof(proof_obj)
    assert result["theorem_in_experimental_calculus"] is False
    assert result["open_assumption_step_ids"] == ["h1", "h2"]
    assert result["truth_table_assignments"] == 4


def test_and_construction_and_elimination_preserve_contexts():
    P, Q = atom("P"), atom("Q")
    data = proof([
        {"id": "h1", "rule": "assume", "formula": P},
        {"id": "h2", "rule": "assume", "formula": Q},
        {"id": "s1", "rule": "and_intro", "left": "h1", "right": "h2"},
        {"id": "s2", "rule": "and_elim_right", "conjunction": "s1"},
    ], Q, "s2")
    result = verify_propositional_proof(data)
    assert result["steps"][2]["unicode"] == "P ∧ Q"
    assert result["steps"][3]["unicode"] == "Q"
    assert result["steps"][3]["open_assumption_step_ids"] == ["h1", "h2"]


def test_or_introduction_does_not_permit_or_elimination():
    P, Q = atom("P"), atom("Q")
    data = proof([
        {"id": "h1", "rule": "assume", "formula": P},
        {"id": "s1", "rule": "or_intro_left", "premise": "h1", "other": Q},
    ], {"op": "or", "left": P, "right": Q}, "s1")
    result = verify_propositional_proof(data)
    assert result["steps"][1]["unicode"] == "P ∨ Q"
    assert result["open_assumption_step_ids"] == ["h1"]
    data["steps"].append({"id": "s2", "rule": "or_elim", "premise": "s1"})
    with pytest.raises(PropositionalProofError, match="Unknown proof rule"):
        verify_propositional_proof(data)


def test_iff_elimination_derives_one_direction_only():
    P, Q = atom("P"), atom("Q")
    data = proof([
        {"id": "h1", "rule": "assume", "formula": {"op": "iff", "left": P, "right": Q}},
        {"id": "s1", "rule": "iff_elim_right", "equivalence": "h1"},
    ], implies(Q, P), "s1")
    result = verify_propositional_proof(data)
    assert result["steps"][1]["unicode"] == "Q ⇒ P"
    assert result["open_assumption_step_ids"] == ["h1"]


@pytest.mark.parametrize("edit", [
    lambda p: p["steps"][2].update({"antecedent": "h2"}),
    lambda p: p["steps"][2].update({"implication": "h1"}),
    lambda p: p["steps"][2].update({"antecedent": "s3"}),
    lambda p: p["steps"][2].update({"antecedent": "unavailable"}),
    lambda p: p["steps"][4].update({"assumption": "s1"}),
    lambda p: p["steps"][4].update({"assumption": "h99"}),
    lambda p: p["steps"][3].update({"conclusion": "s3"}),
    lambda p: p["steps"][1].update({"id": "h1"}),
    lambda p: p["steps"][0].update({"unexpected": "untrusted"}),
    lambda p: p["steps"][2].update({"rule": "magic"}),
    lambda p: p.update({"schema_version": "published"}),
    lambda p: p["provenance"].update({"status": "approved"}),
    lambda p: p.update({"conclusion_step_id": "h1"}),
    lambda p: p["goal"].update({"op": "or"}),
])
def test_wrong_justification_or_claimed_goal_fails_closed(edit):
    data = sample()
    edit(data)
    with pytest.raises(PropositionalProofError):
        verify_propositional_proof(data)


def test_not_every_claimed_goal_is_a_theorem():
    P, Q = atom("P"), atom("Q")
    data = proof([{"id": "h1", "rule": "assume", "formula": P}], Q, "h1")
    with pytest.raises(PropositionalProofError, match="Claimed goal"):
        verify_propositional_proof(data)


def test_deep_formula_is_rejected_before_unbounded_rendering():
    data = sample()
    expr = atom("P")
    for _ in range(MAX_FORMULA_DEPTH + 3):
        expr = {"op": "not", "arg": expr}
    data["goal"] = expr
    with pytest.raises(PropositionalProofError, match="depth limit"):
        verify_propositional_proof(data)


def test_duplicate_hypothesis_cannot_be_disguised_as_two_independent_steps():
    P = atom("P")
    data = proof([
        {"id": "h1", "rule": "assume", "formula": P},
        {"id": "h1", "rule": "assume", "formula": P},
    ], P, "h1")
    with pytest.raises(PropositionalProofError, match="Duplicate step"):
        verify_propositional_proof(data)


def test_boolean_formula_rendering_uses_distinct_logical_notation():
    P, Q = atom("P"), atom("Q")
    tree = {
        "op": "iff",
        "left": {"op": "not", "arg": {"op": "and", "left": P, "right": Q}},
        "right": {"op": "or", "left": {"op": "not", "arg": P}, "right": {"op": "not", "arg": Q}},
    }
    result = render_formula(tree)
    assert result["unicode"] == "¬(P ∧ Q) ⇔ ¬P ∨ ¬Q"
    assert r"\land" in result["latex"]
    assert r"\Leftrightarrow" in result["latex"]
    assert "if and only if" in result["mechanical_text"]
