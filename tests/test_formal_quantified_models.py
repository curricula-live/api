"""Typed quantified class model rendering must never infer role semantics."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from core.formal_quantified_models import TypedRoleError, render_typed_quantified_model

HERE = Path(__file__).resolve().parent
ROLE_FILE = HERE / "fixtures/role-signatures.synthetic.json"
MODEL_FILE = HERE / "fixtures/formal-array.synthetic.json"
ARRAY = "ea8c3f31-8745-52b1-9e29-d5fcf6ab16ba"
STRUCTURE = "50484348-83a3-57b8-bbe4-114b66419300"
INDEX = "b4bf30bd-361a-5121-99f9-2c18afeaa60e"
LABELS = {ARRAY: "Array", STRUCTURE: "Data Structure", INDEX: "Index"}
PREDICATES = {"uses": "uses", "measures": "measures"}


def _jsonl(rows):
    return b"".join(json.dumps(row, sort_keys=True).encode() + b"\n" for row in rows)


def sample():
    model = json.loads(MODEL_FILE.read_text(encoding="utf-8"))
    manifest = json.loads(ROLE_FILE.read_text(encoding="utf-8"))
    concepts = _jsonl([
        {"id": ARRAY, "label": "Array", "slug": "array"},
        {"id": STRUCTURE, "label": "Data Structure", "slug": "data-structure"},
        {"id": INDEX, "label": "Index", "slug": "index"},
    ])
    predicates = _jsonl([{"slug": "uses"}, {"slug": "measures"}])
    manifest["snapshot"]["concepts_sha256"] = "sha256:" + sha256(concepts).hexdigest()
    manifest["snapshot"]["predicates_sha256"] = "sha256:" + sha256(predicates).hexdigest()
    return model, manifest, concepts, predicates


def render(model, manifest, concepts, predicates):
    return render_typed_quantified_model(
        model, manifest,
        concept_labels=LABELS, predicate_labels=PREDICATES,
        concepts_jsonl=concepts, predicates_jsonl=predicates,
        known_statement_ids=set(),
    )


def test_existential_is_well_typed_but_never_proven_by_uses_record():
    model, manifest, concepts, predicates = sample()
    result = render(model, manifest, concepts, predicates)
    assert result["unicode"] == "Array ⊑ (Data Structure ⊓ ∃uses.Index)"
    assert r"\exists" in result["latex"]
    assert result["typed_role_signatures_checked"] is True
    assert result["typed_role_occurrences"] == [{
        "op": "some", "role": "uses",
        "sort": "object_role", "scope": "synthetic_abstract_programming",
        "interpretation": "assumed_not_in_source",
    }]
    assert result["source_evidence_proves_quantifier"] is False
    assert result["may_publish"] is False


def test_universal_quantifier_has_independent_syntax_but_no_source_entailment():
    model, manifest, concepts, predicates = sample()
    model["expression"]["args"][1]["op"] = "only"
    result = render(model, manifest, concepts, predicates)
    assert "∀uses.Index" in result["unicode"]
    assert r"\forall" in result["latex"]
    assert result["role_semantics_verified"] is False


@pytest.mark.parametrize("alter", [
    lambda m, r: r.update({"schema_version": "published"}),
    lambda m, r: r.update({"scope": "synthetic_other"}),
    lambda m, r: r["provenance"].update({"role_semantics_origin": "reviewed"}),
    lambda m, r: r["signatures"][0].update({"role_sort": "data_role"}),
    lambda m, r: r["signatures"][0].update({"property_slug": "invented"}),
    lambda m, r: r["signatures"][0].update({"domain_concept_id": "00000000-0000-4000-8000-000000000000"}),
    lambda m, r: r["signatures"][0].update({"range_concept_id": "00000000-0000-4000-8000-000000000000"}),
    lambda m, r: r["signatures"][0].update({"extra": "trusted"}),
    lambda m, r: r["signatures"].append(deepcopy(r["signatures"][0])),
    lambda m, r: r["snapshot"].update({"concepts_sha256": "sha256:" + "0"*64}),
    lambda m, r: m.update({"scope": "scientific"}),
    lambda m, r: m["expression"]["args"][1].update({"property": "measures"}),
])
def test_invalid_qualifier_or_signature_fails_closed(alter):
    model, manifest, concepts, predicates = sample()
    alter(model, manifest)
    with pytest.raises(TypedRoleError):
        render(model, manifest, concepts, predicates)


def test_registry_snapshot_fingerprint_check_uses_exact_bytes():
    model, manifest, concepts, predicates = sample()
    with pytest.raises(TypedRoleError, match="stale identity registry"):
        render(model, manifest, concepts, predicates + b"\n")


def test_role_signature_does_not_upgrade_canonical_statement_status():
    model, manifest, concepts, predicates = sample()
    model["provenance"]["supporting_statement_ids"] = []
    result = render(model, manifest, concepts, predicates)
    assert result["source_claims_verified"] is False
    assert result["status"] == "synthetic_fixture"
    assert result["role_semantics_verified"] is False
