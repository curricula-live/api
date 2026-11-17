"""IFF introduction requires two independently justified implication directions."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.formal_propositional_proofs import PropositionalProofError, verify_propositional_proof

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "propositional-biconditional.synthetic.json"


def sample():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def atom(name: str) -> dict:
    return {"op": "atom", "name": name}


def imp(p: dict, q: dict) -> dict:
    return {"op": "implies", "left": p, "right": q}


def test_two_directions_produce_only_conditional_biconditional():
    result = verify_propositional_proof(sample())
    assert result["conclusion"]["unicode"] == "P ⇔ Q"
    assert result["steps"][-1]["rule"] == "iff_intro"
    assert result["steps"][-1]["premise_step_ids"] == ["h1", "h2"]
    assert result["theorem_in_experimental_calculus"] is False
    assert result["open_assumption_step_ids"] == ["h1", "h2"]
    assert result["logical_rules_checked"] is True
    assert result["may_publish"] is False
    assert result["scientific_sources_verified"] is False
    assert result["truth_table_assignments"] == 4


def test_closed_p_iff_p_has_no_undischarged_hypotheses():
    p = atom("P")
    cert = sample()
    cert["goal"] = {"op": "iff", "left": p, "right": p}
    cert["steps"] = [
        {"id": "h1", "rule": "assume", "formula": p},
        {"id": "s1", "rule": "imp_intro", "assumption": "h1", "conclusion": "h1"},
        {"id": "s2", "rule": "iff_intro", "left": "s1", "right": "s1"},
    ]
    cert["conclusion_step_id"] = "s2"
    out = verify_propositional_proof(cert)
    assert out["theorem_in_experimental_calculus"] is True
    assert out["open_assumption_step_ids"] == []
    assert out["conclusion"]["unicode"] == "P ⇔ P"


@pytest.mark.parametrize("tamper", [
    lambda p: p["steps"].pop(1),
    lambda p: p["steps"][2].update({"right": "h1"}),
    lambda p: p["steps"][2].update({"right": "unknown"}),
    lambda p: p["steps"][2].update({"left": "s1"}),
    lambda p: p["steps"][1]["formula"].update({"left": atom("R")}),
    lambda p: p["steps"][1]["formula"].update({"right": atom("R")}),
    lambda p: p["steps"][0].update({"rule": "iff_intro"}),
    lambda p: p["steps"][2].update({"rule": "iff_magic"}),
    lambda p: p.update({"goal": imp(atom("P"), atom("Q"))}),
])
def test_iff_fails_if_one_direction_or_proof_is_missing(tamper):
    cert = sample()
    tamper(cert)
    with pytest.raises(PropositionalProofError):
        verify_propositional_proof(cert)


def test_one_implication_is_not_an_equivalence():
    cert = sample()
    cert["steps"] = cert["steps"][:1]
    cert["conclusion_step_id"] = "h1"
    with pytest.raises(PropositionalProofError, match="Claimed goal"):
        verify_propositional_proof(cert)
