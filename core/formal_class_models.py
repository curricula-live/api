"""Pure renderer for the experimental formal-class-model.v0 contract.

This is a class-expression syntax preview, NOT a theorem prover, source
validator, or public endpoint. It accepts synthetic fixtures only.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping
from uuid import UUID


class FormalModelError(ValueError):
    pass


MAX_DEPTH = 10
MAX_NODES = 96
IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")
SCOPE = re.compile(r"^[a-z][a-z0-9_-]{0,79}$")


@dataclass(frozen=True)
class RenderedExpression:
    unicode: str
    latex: str
    plain: str
    priority: int


def _fields(value: object, required: set[str], *, location: str) -> dict:
    if not isinstance(value, dict) or set(value) != required:
        raise FormalModelError(f"{location}: expected exactly {sorted(required)}")
    return value


def _uuid(value: object, *, location: str) -> str:
    if not isinstance(value, str):
        raise FormalModelError(f"{location}: expected UUID string")
    try:
        canonical = str(UUID(value))
    except (ValueError, AttributeError) as exc:
        raise FormalModelError(f"{location}: invalid UUID") from exc
    if canonical != value:
        raise FormalModelError(f"{location}: UUID must use canonical lowercase format")
    return value


def _latex_label(label: str) -> str:
    # Concept/predicate names are user-data, never raw LaTeX commands.
    mapping = {
        "\\": r"\textbackslash{}",
        "{": r"\{", "}": r"\}", "#": r"\#",
        "$": r"\$", "%": r"\%", "&": r"\&",
        "_": r"\_", "^": r"\textasciicircum{}",
        "~": r"\textasciitilde{}",
    }
    escaped = "".join(mapping.get(character, "\\ " if character == " " else character) for character in label)
    return r"\mathrm{" + escaped + "}"


def render_formal_class_model(
    model: dict,
    *,
    concept_labels: Mapping[str, str],
    predicate_labels: Mapping[str, str],
    known_statement_ids: set[str] | None = None,
) -> dict:
    """Render typed syntax with explicit semantic status and parenthesization.

    The model must be a synthetic fixture. Returning an expression never
    upgrades a class relation into an accepted scientific proposition.
    """
    _fields(
        model,
        {"schema_version", "subject_concept_id", "scope", "relation", "expression", "provenance"},
        location="model",
    )
    if model["schema_version"] != "formal-class-model.v0":
        raise FormalModelError("Unsupported model schema version")
    if not isinstance(model["scope"], str) or not SCOPE.fullmatch(model["scope"]):
        raise FormalModelError("Invalid or unspecified scope")
    if model["relation"] not in ("necessary", "equivalent"):
        raise FormalModelError("Relation must be necessary or equivalent")
    subject = _uuid(model["subject_concept_id"], location="subject")
    if subject not in concept_labels:
        raise FormalModelError("Unknown subject concept UUID")
    provenance = _fields(
        model["provenance"], {"status", "supporting_statement_ids"}, location="provenance"
    )
    if provenance["status"] != "synthetic_fixture":
        raise FormalModelError("Only explicit synthetic_fixture models can be previewed")
    supporting = provenance["supporting_statement_ids"]
    if not isinstance(supporting, list) or len(supporting) > 32:
        raise FormalModelError("Invalid supporting statement IDs")
    for item in supporting:
        _uuid(item, location="supporting statement")
        if known_statement_ids is not None and item not in known_statement_ids:
            raise FormalModelError("Unknown supporting statement UUID")
    if len(set(supporting)) != len(supporting):
        raise FormalModelError("Duplicate supporting statement ID")

    count = 0

    def visit(expression: object, depth: int) -> RenderedExpression:
        nonlocal count
        if depth > MAX_DEPTH:
            raise FormalModelError("Expression exceeds maximum depth")
        count += 1
        if count > MAX_NODES:
            raise FormalModelError("Expression exceeds maximum nodes")
        if not isinstance(expression, dict):
            raise FormalModelError("Expected expression object")
        op = expression.get("op")
        if op == "concept":
            _fields(expression, {"op", "concept_id"}, location="concept expression")
            identifier = _uuid(expression["concept_id"], location="concept expression")
            if identifier not in concept_labels:
                raise FormalModelError("Unknown expression concept UUID")
            label = concept_labels[identifier]
            if not isinstance(label, str) or not label.strip() or len(label) > 200:
                raise FormalModelError("Invalid concept label")
            return RenderedExpression(label, _latex_label(label), label, 5)

        if op in ("and", "or"):
            _fields(expression, {"op", "args"}, location=f"{op} expression")
            args = expression["args"]
            if not isinstance(args, list) or not (2 <= len(args) <= 24):
                raise FormalModelError(f"{op} needs 2–24 arguments")
            members = [visit(arg, depth + 1) for arg in args]
            priority = 2 if op == "and" else 1
            unicode_op = " ⊓ " if op == "and" else " ⊔ "
            latex_op = r"\sqcap " if op == "and" else r"\sqcup "
            plain_op = " and " if op == "and" else " or "
            def parenthesize(item: RenderedExpression) -> tuple[str, str, str]:
                if item.priority >= priority:
                    return item.unicode, item.latex, item.plain
                return f"({item.unicode})", r"\left(" + item.latex + r"\right)", f"({item.plain})"
            u, l, p = zip(*(parenthesize(m) for m in members))
            return RenderedExpression(
                unicode_op.join(u), latex_op.join(l), plain_op.join(p), priority
            )

        if op == "not":
            _fields(expression, {"op", "arg"}, location="negation")
            nested = visit(expression["arg"], depth + 1)
            if nested.priority < 3:
                return RenderedExpression(
                    f"¬({nested.unicode})",
                    r"\neg\left(" + nested.latex + r"\right)",
                    f"not ({nested.plain})", 3,
                )
            return RenderedExpression(
                "¬" + nested.unicode, r"\neg " + nested.latex, "not " + nested.plain, 3
            )

        if op in ("some", "only"):
            _fields(expression, {"op", "property", "filler"}, location="relation restriction")
            property_name = expression["property"]
            if not isinstance(property_name, str) or not IDENTIFIER.fullmatch(property_name) or len(property_name) > 64:
                raise FormalModelError("Invalid predicate identifier")
            if property_name not in predicate_labels:
                raise FormalModelError("Unknown predicate in restriction")
            filler = visit(expression["filler"], depth + 1)
            if not isinstance(predicate_labels[property_name], str):
                raise FormalModelError("Invalid predicate label")
            symbol = "∃" if op == "some" else "∀"
            latex_symbol = r"\exists" if op == "some" else r"\forall"
            f_unicode = filler.unicode if filler.priority >= 4 else f"({filler.unicode})"
            f_latex = filler.latex if filler.priority >= 4 else r"\left(" + filler.latex + r"\right)"
            f_plain = filler.plain if filler.priority >= 4 else f"({filler.plain})"
            label = predicate_labels[property_name]
            plain_label = f"some {label} relation to" if op == "some" else f"only {label} relations to"
            return RenderedExpression(
                f"{symbol}{label}.{f_unicode}",
                latex_symbol + r"\," + _latex_label(label) + "." + f_latex,
                f"{plain_label} {f_plain}", 4
            )

        raise FormalModelError("Unknown formal class-expression operator")

    expression = visit(model["expression"], 1)
    label = concept_labels[subject]
    relation = model["relation"]
    sign = "⊑" if relation == "necessary" else "≡"
    latex_sign = r"\sqsubseteq" if relation == "necessary" else r"\equiv"
    if expression.priority < 4:
        expression_unicode = f"({expression.unicode})"
        expression_latex = r"\left(" + expression.latex + r"\right)"
    else:
        expression_unicode, expression_latex = expression.unicode, expression.latex
    return {
        "schema_version": model["schema_version"],
        "scope": model["scope"],
        "relation": relation,
        "unicode": f"{label} {sign} {expression_unicode}",
        "latex": _latex_label(label) + " " + latex_sign + " " + expression_latex,
        "mechanical_text": (
            f"Necessary conditions for {label}: {expression.plain}."
            if relation == "necessary"
            else f"{label} is defined equivalently by: {expression.plain}."
        ),
        "syntax_tree": model["expression"],
        "referenced_statement_ids": list(supporting),
        "operator_nodes": count,
        "status": "synthetic_fixture",
        "well_formed": True,
        "logical_soundness_verified": False,
        "source_claims_verified": False,
        "may_publish": False,
    }
