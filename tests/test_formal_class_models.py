"""Rendering of synthetic formal class models is generic and nonpublishing."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.formal_class_models import FormalModelError, render_formal_class_model

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "formal-array.synthetic.json"
ARRAY = "ea8c3f31-8745-52b1-9e29-d5fcf6ab16ba"
STRUCTURE = "50484348-83a3-57b8-bbe4-114b66419300"
INDEX = "b4bf30bd-361a-5121-99f9-2c18afeaa60e"
LABELS = {ARRAY: "Array", STRUCTURE: "Data Structure", INDEX: "Index"}
PREDICATES = {"uses": "uses"}


def sample():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def render(model):
    return render_formal_class_model(
        model,
        concept_labels=LABELS,
        predicate_labels=PREDICATES,
        known_statement_ids=set(),
    )


def test_can_render_class_axiom_in_unicode_latex_and_mechanical_language():
    result = render(sample())
    assert result["unicode"] == "Array ⊑ (Data Structure ⊓ ∃uses.Index)"
    assert result["latex"] == (
        r"\mathrm{Array} \sqsubseteq \left("
        r"\mathrm{Data\ Structure}\sqcap \exists\,\mathrm{uses}.\mathrm{Index}\right)"
    )
    assert result["mechanical_text"] == (
        "Necessary conditions for Array: Data Structure and some uses relation to Index."
    )
    assert result["operator_nodes"] == 4
    assert result["may_publish"] is False
    assert result["source_claims_verified"] is False
    assert result["logical_soundness_verified"] is False


def test_rendering_preserves_disjunction_negation_and_universal_restriction():
    m = sample()
    ref = {"op": "concept", "concept_id": STRUCTURE}
    m["relation"] = "equivalent"
    m["expression"] = {
        "op": "or",
        "args": [
            {"op": "not", "arg": ref},
            {"op": "only", "property": "uses", "filler": ref},
        ],
    }
    result = render(m)
    assert result["unicode"] == "Array ≡ (¬Data Structure ⊔ ∀uses.Data Structure)"
    assert "\\equiv" in result["latex"] and "\\forall" in result["latex"]
    assert "not Data Structure or only uses relations to Data Structure" in result["mechanical_text"]


def test_parentheses_preserve_operator_precedence():
    m = sample()
    ref = {"op": "concept", "concept_id": STRUCTURE}
    m["expression"] = {
        "op": "and",
        "args": [
            {"op": "or", "args": [ref, {"op": "concept", "concept_id": INDEX}]},
            ref,
        ],
    }
    assert "(Data Structure ⊔ Index) ⊓ Data Structure" in render(m)["unicode"]


@pytest.mark.parametrize("change", [
    lambda m: m.update({"schema_version": "wrong"}),
    lambda m: m.update({"relation": "iff"}),
    lambda m: m.update({"scope": " "}),
    lambda m: m["provenance"].update({"status": "approved"}),
    lambda m: m["expression"].update({"op": "unsupported_operator"}),
    lambda m: m["expression"]["args"][1].update({"property": "invented_predicate"}),
    lambda m: m["expression"].update({"unexpected": "injection"}),
    lambda m: m["provenance"]["supporting_statement_ids"].append("bad-uuid"),
])
def test_unknown_or_invalid_metadata_fails_closed(change):
    model = sample()
    change(model)
    with pytest.raises(FormalModelError):
        render(model)


def test_unknown_references_and_unverified_supporting_statements_rejected():
    model = sample()
    model["subject_concept_id"] = "00000000-0000-4000-8000-000000000000"
    with pytest.raises(FormalModelError, match="Unknown subject"):
        render(model)
    model = sample()
    model["provenance"]["supporting_statement_ids"] = ["048adf33-0701-43de-998f-20c299388f51"]
    with pytest.raises(FormalModelError, match="Unknown supporting statement"):
        render(model)


def test_renderer_escapes_latex_from_user_supplied_labels():
    model = sample()
    labels = {**LABELS, STRUCTURE: r"Unsafe\\input_%"}
    result = render_formal_class_model(
        model, concept_labels=labels, predicate_labels=PREDICATES
    )
    assert r"\textbackslash{}" in result["latex"]
    assert r"\_" in result["latex"]
    assert r"\%" in result["latex"]
    assert r"\input" not in result["latex"]
