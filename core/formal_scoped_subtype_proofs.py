"""Exact-UUID, scope-conditional subtype transitivity proof checker.

This is a typed *rule experiment*, not a scientific knowledge publisher.
Canonical statement JSONL does not contain reviewed subtype semantics or a
scope field. Every per-premise assumed_scope is supplied externally as an
explicit, unverified hypothesis. Matching strings establish compatibility
of the *hypothesis labels*, NOT source-backed semantic equivalence.

The sole rule is:
  subtype_of(A,B) @ scope S, subtype_of(B,C) @ scope S
  ---------------------------------------------------- [subtype_transitivity]
                 subtype_of(A,C) @ scope S

No other predicate, inverse direction, or cross-scope inference is permitted.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re

from core.formal_recorded_statement_bridge import _read_jsonl, _fields, _uuid

CONTRACT_VERSION = "formal-scoped-subtype-proof.v0"
SCOPE = re.compile(r"^hypothetical_[a-z][a-z0-9_]{0,61}$")
STEP_ID = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
FINGERPRINT = re.compile(r"^sha256:[a-f0-9]{64}$")
MAX_STEPS = 64


class ScopedSubtypeProofError(ValueError):
    pass


@dataclass(frozen=True)
class ScopedSubtype:
    subject_id: str
    object_id: str
    scope: str
    premise_ids: tuple[str, ...]


def verify_scoped_subtype_proof(
    certificate: dict,
    *,
    concepts_jsonl: bytes,
    statements_jsonl: bytes,
) -> dict:
    """Check one hypothetical scoped proof against a pinned canonical snapshot.

    The returned claim is only valid CONDITIONALLY on the recorded premises
    being correct and each assumed scope truly having subtype semantics.
    A verifier cannot learn these semantics from the legacy JSONL files.
    """
    try:
        _fields(
            certificate,
            {"schema_version", "scope", "provenance", "snapshot",
             "goal", "steps", "conclusion_step_id"},
            "subtype proof",
        )
        if certificate["schema_version"] != CONTRACT_VERSION:
            raise ScopedSubtypeProofError("Unsupported proof contract version")
        scope = certificate["scope"]
        if not isinstance(scope, str) or not SCOPE.fullmatch(scope):
            raise ScopedSubtypeProofError("Only explicit hypothetical scopes are allowed")
        _fields(
            certificate["provenance"],
            {"status", "source_scientific_review", "scope_origin"},
            "provenance",
        )
        if certificate["provenance"] != {
            "status": "synthetic_fixture",
            "source_scientific_review": "not_established",
            "scope_origin": "assumed_not_in_source",
        }:
            raise ScopedSubtypeProofError("No verified source/semantic status is authorized")

        _fields(certificate["snapshot"], {"concepts_sha256", "statements_sha256"}, "snapshot")
        for label, payload in (("concepts", concepts_jsonl), ("statements", statements_jsonl)):
            digest = certificate["snapshot"][f"{label}_sha256"]
            if not isinstance(digest, str) or not FINGERPRINT.fullmatch(digest):
                raise ScopedSubtypeProofError(f"Invalid {label} snapshot hash")
            if "sha256:" + sha256(payload).hexdigest() != digest:
                raise ScopedSubtypeProofError(f"{label}: source snapshot mismatch")

        concept_rows = _read_jsonl(concepts_jsonl, "concepts")
        statement_rows = _read_jsonl(statements_jsonl, "statements")
        concept_by_id = {row["id"]: row for row in concept_rows}
        statement_by_id = {row["id"]: row for row in statement_rows}
        if len(concept_rows) != len(concept_by_id) or len(statement_rows) != len(statement_by_id):
            raise ScopedSubtypeProofError("Duplicate canonical concept/statement UUID")

        _fields(certificate["goal"], {"subject_concept_id", "predicate", "object_concept_id"}, "goal")
        goal = certificate["goal"]
        start_id = _uuid(goal["subject_concept_id"], "goal subject")
        end_id = _uuid(goal["object_concept_id"], "goal object")
        if goal["predicate"] != "subtype_of":
            raise ScopedSubtypeProofError("Only subtype_of conclusions are supported")
        if start_id not in concept_by_id or end_id not in concept_by_id:
            raise ScopedSubtypeProofError("Unknown concept in conclusion")

        steps = certificate["steps"]
        if not isinstance(steps, list) or not (3 <= len(steps) <= MAX_STEPS):
            raise ScopedSubtypeProofError("Proof needs 3–64 ordered steps")
        steps_by_id: dict[str, ScopedSubtype] = {}
        trace: list[dict] = []
        recorded_seen: set[str] = set()
        rule_count = 0

        for raw in steps:
            if not isinstance(raw, dict):
                raise ScopedSubtypeProofError("Proof step must be an object")
            rule, identifier = raw.get("rule"), raw.get("id")
            if not isinstance(identifier, str) or not STEP_ID.fullmatch(identifier):
                raise ScopedSubtypeProofError("Invalid proof step identifier")
            if identifier in steps_by_id:
                raise ScopedSubtypeProofError("Duplicate proof step ID")

            if rule == "recorded_subtype":
                _fields(raw, {"id", "rule", "statement_id", "assumed_scope"}, identifier)
                sid = _uuid(raw["statement_id"], "premise statement")
                if sid in recorded_seen:
                    raise ScopedSubtypeProofError("Duplicated recorded premise UUID")
                recorded_seen.add(sid)
                if raw["assumed_scope"] != scope:
                    raise ScopedSubtypeProofError("Recorded premise has incompatible assumed scope")
                source = statement_by_id.get(sid)
                if source is None:
                    raise ScopedSubtypeProofError("Missing original canonical statement UUID")
                if source.get("predicate") != "subtype_of":
                    raise ScopedSubtypeProofError("Recorded assertion has a different predicate")
                subject = source.get("subject")
                obj = source.get("object")
                if not isinstance(subject, dict) or not isinstance(obj, dict):
                    raise ScopedSubtypeProofError("Recorded statement has malformed endpoints")
                if subject.get("kind") != "concept" or obj.get("kind") != "concept":
                    raise ScopedSubtypeProofError("Only concept-to-concept subtype statements supported")
                a = _uuid(subject.get("id"), "recorded subject")
                b = _uuid(obj.get("id"), "recorded object")
                if a not in concept_by_id or b not in concept_by_id:
                    raise ScopedSubtypeProofError("Recorded statement contains unknown concept UUID")
                typed = ScopedSubtype(a, b, scope, (sid,))
                parents: list[str] = []

            elif rule == "subtype_transitivity":
                _fields(raw, {"id", "rule", "left", "right"}, identifier)
                left_id, right_id = raw["left"], raw["right"]
                if (
                    not isinstance(left_id, str) or not isinstance(right_id, str)
                    or left_id not in steps_by_id or right_id not in steps_by_id
                ):
                    raise ScopedSubtypeProofError("Rule references missing/future proof steps")
                left, right = steps_by_id[left_id], steps_by_id[right_id]
                if left.scope != right.scope or left.scope != scope:
                    raise ScopedSubtypeProofError("Cannot compose subtype premises across scopes")
                if left.object_id != right.subject_id:
                    raise ScopedSubtypeProofError(
                        "Transitivity requires left.target == right.subject in this direction"
                    )
                typed = ScopedSubtype(
                    left.subject_id, right.object_id, scope, left.premise_ids + right.premise_ids
                )
                parents = [left_id, right_id]
                rule_count += 1

            else:
                raise ScopedSubtypeProofError("Unknown or unauthorized semantic rule")

            steps_by_id[identifier] = typed
            trace.append({
                "id": identifier,
                "rule": rule,
                "scope": scope,
                "subject_concept_id": typed.subject_id,
                "subject_label": concept_by_id[typed.subject_id]["label"],
                "predicate": "subtype_of",
                "object_concept_id": typed.object_id,
                "object_label": concept_by_id[typed.object_id]["label"],
                "premise_step_ids": parents,
                "original_statement_ids": list(typed.premise_ids),
                "status": "conditional_on_recorded_premises_and_assumed_scope",
            })

        final_step_id = certificate["conclusion_step_id"]
        if not isinstance(final_step_id, str) or final_step_id not in steps_by_id:
            raise ScopedSubtypeProofError("Conclusion refers to nonexistent step")
        final = steps_by_id[final_step_id]
        if trace[next(i for i, item in enumerate(trace) if item["id"] == final_step_id)]["rule"] != "subtype_transitivity":
            raise ScopedSubtypeProofError("Conclusion must be an explicit derived transitivity step")
        if not rule_count:
            raise ScopedSubtypeProofError("No semantic rule was applied")
        if (final.subject_id, final.object_id) != (start_id, end_id):
            raise ScopedSubtypeProofError("Claimed goal differs from derived relation")

        # A deterministic, checkable proof fingerprint records the entire
        # certificate, including the hypothesis that supplied the scope.
        digest = sha256(json.dumps(
            certificate, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")).hexdigest()

        return {
            "schema_version": CONTRACT_VERSION,
            "rule_id": "subtype_transitivity@v0",
            "proof_fingerprint": "sha256:" + digest,
            "source_snapshot": dict(certificate["snapshot"]),
            "scope": scope,
            "scope_origin": "assumed_not_in_source",
            "hypothetical_semantic_rule": (
                "subtype_of(A,B)@S ∧ subtype_of(B,C)@S ⇒ subtype_of(A,C)@S"
            ),
            "original_recorded_premises": list(final.premise_ids),
            "steps": trace,
            "conclusion": {
                "subject_concept_id": final.subject_id,
                "subject_label": concept_by_id[final.subject_id]["label"],
                "predicate": "subtype_of",
                "object_concept_id": final.object_id,
                "object_label": concept_by_id[final.object_id]["label"],
                "scope": scope,
                "status": "conditional_provisional_inference",
            },
            "proof_steps_checked": True,
            "source_scientific_reviewed": False,
            "semantic_scope_source_verified": False,
            "may_publish": False,
            "new_canonical_statement_created": False,
        }

    except (KeyError, TypeError, AttributeError, StopIteration) as error:
        raise ScopedSubtypeProofError("Malformed or incomplete scoped subtype certificate") from error
    except ValueError as error:
        if isinstance(error, ScopedSubtypeProofError):
            raise
        raise ScopedSubtypeProofError(f"Invalid source/proof metadata: {error}") from error


def main() -> None:
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("certificate", type=Path)
    parser.add_argument("--concepts", type=Path, required=True)
    parser.add_argument("--statements", type=Path, required=True)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    proof = json.loads(args.certificate.read_text(encoding="utf-8"))
    outcome = verify_scoped_subtype_proof(
        proof,
        concepts_jsonl=args.concepts.read_bytes(),
        statements_jsonl=args.statements.read_bytes(),
    )
    if args.format == "json":
        print(json.dumps(outcome, indent=2, ensure_ascii=False))
    else:
        print("Scoped subtype proof · HYPOTHETICAL semantic scope")
        for row in outcome["steps"]:
            refs = ", ".join(row["premise_step_ids"]) or "recorded premise"
            print(
                f"{row['id']:>3} {row['subject_label']} ⊑ {row['object_label']}"
                f" [{row['rule']}: {refs}]"
            )
        goal = outcome["conclusion"]
        print("∴", goal["subject_label"], "⊑", goal["object_label"])
        print("Original source premise UUIDs:", ", ".join(outcome["original_recorded_premises"]))
        print("Status:", goal["status"])
        print("Semantic context certified by source:", outcome["semantic_scope_source_verified"])
        print("May publish:", outcome["may_publish"])


if __name__ == "__main__":
    main()
