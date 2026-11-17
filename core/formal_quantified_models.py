"""Render quantified class expressions only against explicit typed role signatures.

A predicate slug in the canonical graph is NOT an OWL/DL object property by
default. This adapter requires a scope-matched synthetic role declaration,
snapshot-pinned identity registries and an object-valued role for ∃R.C/∀R.C.
It does not infer an existential witness or a universal restriction from a
recorded concept-to-concept 'uses' edge.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Mapping
from uuid import UUID
import json
import re

from core.formal_class_models import FormalModelError, render_formal_class_model

SCOPE = re.compile(r"^synthetic_[a-z][a-z0-9_]{0,71}$")
HASH = re.compile(r"^sha256:[a-f0-9]{64}$")
PROPERTY = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class TypedRoleError(ValueError):
    pass


def _fields(obj: object, keys: set[str], context: str) -> dict:
    if not isinstance(obj, dict) or set(obj) != keys:
        raise TypedRoleError(f"{context}: expected exactly {sorted(keys)}")
    return obj


def _records(payload: bytes, key: str) -> set[str]:
    if not isinstance(payload, bytes) or len(payload) > 8 * 1024 * 1024:
        raise TypedRoleError("Invalid or oversized registry")
    try:
        rows = [json.loads(line) for line in payload.decode().splitlines() if line.strip()]
        ids = {r[key] for r in rows}
    except (ValueError, UnicodeError, TypeError, KeyError) as exc:
        raise TypedRoleError("Invalid registry data") from exc
    if len(ids) != len(rows):
        raise TypedRoleError("Duplicated canonical registry identity")
    return ids


def _uuid(value: object) -> str:
    if not isinstance(value, str):
        raise TypedRoleError("Domain/range concept identity must be canonical UUID")
    try:
        if str(UUID(value)) != value:
            raise ValueError()
    except (ValueError, AttributeError) as exc:
        raise TypedRoleError("Invalid domain/range concept UUID") from exc
    return value


def render_typed_quantified_model(
    model: dict,
    role_manifest: dict,
    *,
    concept_labels: Mapping[str, str],
    predicate_labels: Mapping[str, str],
    concepts_jsonl: bytes,
    predicates_jsonl: bytes,
    known_statement_ids: set[str] | None = None,
) -> dict:
    _fields(
        role_manifest,
        {"schema_version", "scope", "provenance", "snapshot", "signatures"},
        "roles",
    )
    if role_manifest["schema_version"] != "formal-role-signatures.v0":
        raise TypedRoleError("Unknown role signature version")
    if not isinstance(model, dict):
        raise TypedRoleError("Model must be a structured class-expression object")
    scope = role_manifest["scope"]
    if not isinstance(scope, str) or not SCOPE.fullmatch(scope) or model.get("scope") != scope:
        raise TypedRoleError("Model must share the hypothetical role scope")
    if _fields(
        role_manifest["provenance"],
        {"status", "role_semantics_origin"},
        "provenance",
    ) != {"status": "synthetic_fixture", "role_semantics_origin": "assumed_not_in_source"}:
        raise TypedRoleError("Role semantics may not be certified here")

    snapshot = _fields(
        role_manifest["snapshot"], {"concepts_sha256", "predicates_sha256"}, "snapshot"
    )
    for label, payload in (("concepts", concepts_jsonl), ("predicates", predicates_jsonl)):
        digest = snapshot[f"{label}_sha256"]
        if not isinstance(digest, str) or not HASH.fullmatch(digest):
            raise TypedRoleError("Invalid canonical registry digest")
        if digest != "sha256:" + sha256(payload).hexdigest():
            raise TypedRoleError(f"{label}: stale identity registry")

    concept_ids = _records(concepts_jsonl, "id")
    predicate_names = _records(predicates_jsonl, "slug")
    signatures = role_manifest["signatures"]
    if not isinstance(signatures, list) or not 1 <= len(signatures) <= 24:
        raise TypedRoleError("Invalid role signature count")
    typed: dict[str, dict] = {}
    for item in signatures:
        _fields(
            item, {"property_slug", "role_sort", "domain_concept_id", "range_concept_id"},
            "role signature",
        )
        name, sort = item["property_slug"], item["role_sort"]
        if not isinstance(name, str) or not PROPERTY.fullmatch(name):
            raise TypedRoleError("Invalid role name")
        if name not in predicate_names:
            raise TypedRoleError(f"Role {name} is not a canonical predicate identity")
        if name in typed or sort not in ("object_role", "data_role"):
            raise TypedRoleError("Duplicate or unknown role kind")
        for field in ("domain_concept_id", "range_concept_id"):
            value = item[field]
            if value is not None and _uuid(value) not in concept_ids:
                raise TypedRoleError("Domain/range references unknown canonical concept")
        if sort == "data_role" and item["range_concept_id"] is not None:
            raise TypedRoleError("A data role cannot use a class-valued range")
        typed[name] = item

    quantifiers: list[dict] = []

    def walk(expr: dict) -> None:
        op = expr["op"]
        if op in ("some", "only"):
            name = expr["property"]
            signature = typed.get(name)
            if signature is None:
                raise TypedRoleError(f"No scoped role declaration for {name}")
            if signature["role_sort"] != "object_role":
                raise TypedRoleError("∃R.C and ∀R.C require an individual-valued object role")
            quantifiers.append({
                "op": op, "role": name,
                "sort": "object_role", "scope": scope,
                "interpretation": "assumed_not_in_source",
            })
            walk(expr["filler"])
        elif op in ("and", "or"):
            for child in expr["args"]:
                walk(child)
        elif op == "not":
            walk(expr["arg"])

    try:
        rendered = render_formal_class_model(
            model,
            concept_labels=concept_labels,
            predicate_labels=predicate_labels,
            known_statement_ids=known_statement_ids,
        )
    except FormalModelError as exc:
        raise TypedRoleError(str(exc)) from exc
    referenced = set()

    def refs(expr: dict) -> None:
        if expr["op"] == "concept":
            referenced.add(expr["concept_id"])
        elif expr["op"] in ("some", "only"):
            refs(expr["filler"])
        elif expr["op"] in ("and", "or"):
            for arg in expr["args"]:
                refs(arg)
        elif expr["op"] == "not":
            refs(expr["arg"])

    refs(model["expression"])
    if (referenced | {model["subject_concept_id"]}) - concept_ids:
        raise TypedRoleError("Class model refers to concept outside pinned registry")
    walk(model["expression"])
    return {
        **rendered,
        "typed_role_signatures_checked": True,
        "typed_role_occurrences": quantifiers,
        "role_semantics_verified": False,
        "source_evidence_proves_quantifier": False,
        "scope_origin": "assumed_not_in_source",
        "may_publish": False,
    }
