"""Bridge *recorded* canonical statements into synthetic propositional proofs.

Not a scientific inference engine or a database publisher: an atom P means
"the particular statement UUID is assumed", not "its predicate has been
proved to be scientifically true". The proof checker only proves formulas
over these named atoms.

Consumes exact canonical JSONL BYTES; verifies SHA-256 snapshot identity.
No filesystem/database access, no unreviewed inference rules, no HTTP.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from uuid import UUID

from core.formal_propositional_proofs import (
    PropositionalProofError,
    verify_propositional_proof,
)

VERSION = "formal-statement-bindings.v0"
ATOM_NAME = re.compile(r"^[A-Z][A-Za-z0-9_]{0,31}$")
DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")


class RecordedStatementBindingError(ValueError):
    pass


def _fields(value: object, expected: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != expected:
        raise RecordedStatementBindingError(f"{label}: expected exactly {sorted(expected)}")
    return value


def _uuid(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise RecordedStatementBindingError(f"{label}: expected UUID")
    try:
        if str(UUID(value)) != value:
            raise ValueError("noncanonical UUID")
    except (ValueError, AttributeError) as exc:
        raise RecordedStatementBindingError(f"{label}: invalid UUID") from exc
    return value


def _read_jsonl(data: bytes, label: str) -> list[dict]:
    if not isinstance(data, bytes) or len(data) > 8 * 1024 * 1024:
        raise RecordedStatementBindingError(f"{label}: invalid snapshot bytes")
    try:
        rows = [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]
    except (ValueError, UnicodeError) as exc:
        raise RecordedStatementBindingError(f"{label}: invalid JSONL") from exc
    if not all(isinstance(row, dict) for row in rows):
        raise RecordedStatementBindingError(f"{label}: expected JSON objects")
    return rows


def _all_atoms(expression: dict, names: set[str]) -> None:
    op = expression["op"]
    if op == "atom":
        names.add(expression["name"])
    elif op == "not":
        _all_atoms(expression["arg"], names)
    elif op in ("and", "or", "implies", "iff"):
        _all_atoms(expression["left"], names)
        _all_atoms(expression["right"], names)


def verify_recorded_statement_proof(
    certificate: dict,
    bindings: dict,
    *,
    concepts_jsonl: bytes,
    statements_jsonl: bytes,
) -> dict:
    """Verify exact recorded premises and a conditional propositional proof."""
    _fields(
        bindings, {"schema_version", "scope", "provenance", "snapshot", "bindings"},
        "binding manifest",
    )
    if bindings["schema_version"] != VERSION or bindings["scope"] != "provisional_canonical_graph":
        raise RecordedStatementBindingError("Unsupported source-binding version or scope")
    _fields(bindings["provenance"], {"status", "source_scientific_review"}, "provenance")
    if (
        bindings["provenance"]["status"] != "synthetic_fixture"
        or bindings["provenance"]["source_scientific_review"] != "not_established"
    ):
        raise RecordedStatementBindingError("Scientific review cannot be certified here")

    _fields(bindings["snapshot"], {"concepts_sha256", "statements_sha256"}, "snapshot")
    for name, content in (("concepts", concepts_jsonl), ("statements", statements_jsonl)):
        recorded = bindings["snapshot"][f"{name}_sha256"]
        if not isinstance(recorded, str) or not DIGEST.fullmatch(recorded):
            raise RecordedStatementBindingError(f"{name}: invalid snapshot fingerprint")
        if recorded != "sha256:" + sha256(content).hexdigest():
            raise RecordedStatementBindingError(f"{name}: canonical snapshot mismatch")

    concepts = _read_jsonl(concepts_jsonl, "concepts")
    statements = _read_jsonl(statements_jsonl, "statements")
    concepts_by_id = {row["id"]: row for row in concepts}
    statements_by_id = {row["id"]: row for row in statements}
    if len(concepts_by_id) != len(concepts) or len(statements_by_id) != len(statements):
        raise RecordedStatementBindingError("Canonical UUID is not unique")

    entries = bindings["bindings"]
    if not isinstance(entries, list) or not (1 <= len(entries) <= 16):
        raise RecordedStatementBindingError("Expected 1–16 atom bindings")
    atoms: dict[str, dict] = {}
    referenced_ids: set[str] = set()
    for entry in entries:
        _fields(entry, {"atom", "statement_id"}, "atom binding")
        atom, sid = entry["atom"], _uuid(entry["statement_id"], "statement")
        if not isinstance(atom, str) or not ATOM_NAME.fullmatch(atom):
            raise RecordedStatementBindingError("Invalid atom identifier")
        if atom in atoms or sid in referenced_ids:
            raise RecordedStatementBindingError("Duplicate atom or statement identity")
        referenced_ids.add(sid)
        statement = statements_by_id.get(sid)
        if statement is None:
            raise RecordedStatementBindingError(f"Missing canonical statement UUID: {sid}")
        subject, obj = statement.get("subject"), statement.get("object")
        if not isinstance(subject, dict) or not isinstance(obj, dict):
            raise RecordedStatementBindingError("Malformed canonical statement reference")
        if subject.get("kind") != "concept" or obj.get("kind") != "concept":
            raise RecordedStatementBindingError("Only concept-to-concept statements are supported")
        source, target = subject.get("id"), obj.get("id")
        if source not in concepts_by_id or target not in concepts_by_id:
            raise RecordedStatementBindingError("Recorded statement references unknown concept identity")
        if not isinstance(statement.get("predicate"), str) or not statement["predicate"]:
            raise RecordedStatementBindingError("Malformed canonical predicate")
        atoms[atom] = {
            "atom": atom,
            "statement_id": sid,
            "subject_id": source,
            "subject": concepts_by_id[source]["label"],
            "subject_slug": concepts_by_id[source]["slug"],
            "predicate": statement["predicate"],
            "object_id": target,
            "object": concepts_by_id[target]["label"],
            "object_slug": concepts_by_id[target]["slug"],
            "recorded_claim_text": (
                f"{concepts_by_id[source]['label']} {statement['predicate']} "
                f"{concepts_by_id[target]['label']}"
            ),
            "scientific_status": "recorded_not_reviewed",
        }

    try:
        verified = verify_propositional_proof(certificate)
    except PropositionalProofError as exc:
        raise RecordedStatementBindingError(f"Invalid propositional proof: {exc}") from exc

    used: set[str] = set()
    for step in verified["steps"]:
        _all_atoms(step["formula"], used)
    if used != set(atoms):
        raise RecordedStatementBindingError(
            f"Atom mapping differs from proof syntax: missing {sorted(used - set(atoms))}, "
            f"unused {sorted(set(atoms) - used)}"
        )

    assumption_to_statement: dict[str, str] = {}
    for step in verified["steps"]:
        if step["rule"] != "assume":
            continue
        if step["formula"]["op"] != "atom":
            raise RecordedStatementBindingError(
                "A recorded assertion can only enter as one atomic assumption"
            )
        assumption_to_statement[step["id"]] = atoms[step["formula"]["name"]]["statement_id"]

    source_assumptions = [
        {
            "assumption_step_id": step_id,
            "statement_id": assumption_to_statement[step_id],
            "recorded_claim": atoms[next(
                atom for atom, fact in atoms.items()
                if fact["statement_id"] == assumption_to_statement[step_id]
            )]["recorded_claim_text"],
            "source_scientific_review": "not_established",
        }
        for step_id in verified["open_assumption_step_ids"]
    ]

    return {
        "schema_version": VERSION,
        "source_scope": bindings["scope"],
        "snapshots": dict(bindings["snapshot"]),
        "atom_bindings": [atoms[name] for name in sorted(atoms)],
        "propositional_proof": verified,
        "open_recorded_assumptions": source_assumptions,
        "logical_status": (
            "conditional_on_recorded_statements"
            if source_assumptions else "closed_synthetic_propositional_theorem"
        ),
        "propositional_steps_verified": True,
        "semantic_graph_rules_applied": [],
        "derived_graph_relations": [],
        "scientific_claims_verified": False,
        "authorizes_new_canonical_claim": False,
        "may_publish": False,
    }


def main() -> None:
    """Produce an inspectable, nonpublishing conditional derivation dossier."""
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--concepts", required=True, type=Path, help="Canonical concepts.jsonl")
    parser.add_argument("--statements", required=True, type=Path, help="Canonical statements.jsonl")
    parser.add_argument("--bindings", required=True, type=Path, help="Synthetic atom-to-statement manifest")
    parser.add_argument("--proof", required=True, type=Path, help="Synthetic propositional certificate")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    result = verify_recorded_statement_proof(
        json.loads(args.proof.read_text(encoding="utf-8")),
        json.loads(args.bindings.read_text(encoding="utf-8")),
        concepts_jsonl=args.concepts.read_bytes(),
        statements_jsonl=args.statements.read_bytes(),
    )
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print("Provisional canonical graph → synthetic propositional proof")
    print("Recorded hypotheses:")
    for row in result["atom_bindings"]:
        print(f"  {row['atom']}: {row['recorded_claim_text']}  [{row['statement_id']}]")
    print("Verified propositional steps:")
    for step in result["propositional_proof"]["steps"]:
        refs = ", ".join(step["premise_step_ids"]) or "assumption"
        print(f"  {step['id']}: {step['unicode']}  [{step['rule']}: {refs}]")
    print("Conclusion:", result["propositional_proof"]["conclusion"]["unicode"])
    print("Status:", result["logical_status"])
    print(
        "Open canonical premises:",
        ", ".join(row["statement_id"] for row in result["open_recorded_assumptions"]) or "none",
    )
    print("Derived new concept-to-concept claims:", len(result["derived_graph_relations"]))
    print("May publish:", result["may_publish"])


if __name__ == "__main__":
    main()
