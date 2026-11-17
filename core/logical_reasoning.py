"""Checked logical schemas for concept-page previews, independent of ontology facts.

Run python -m core.logical_reasoning to export the deterministic web artifact.
The formulas are schematic propositions: P/Q/R stand for arbitrary Boolean
propositions, not asserted properties of a particular canonical concept.
"""
from __future__ import annotations

from itertools import product
import json

from core.formal_propositional_proofs import (
    VERSION, verify_propositional_proof, _evaluate,
)


def atom(name):
    return {"op": "atom", "name": name}


def binary(op, left, right):
    return {"op": op, "left": left, "right": right}


def neg(arg):
    return {"op": "not", "arg": arg}


P, Q, R = (atom(name) for name in ("P", "Q", "R"))


class Certificate:
    def __init__(self):
        self.steps = []

    def add(self, rule, **fields):
        identifier = f"s{len(self.steps) + 1}"
        self.steps.append({"id": identifier, "rule": rule, **fields})
        return identifier

    def assume(self, formula):
        return self.add("assume", formula=formula)

    def finish(self, goal):
        return {
            "schema_version": VERSION, "scope": "boolean_propositional_schemas",
            "provenance": {"status": "synthetic_fixture"}, "goal": goal,
            "steps": self.steps, "conclusion_step_id": self.steps[-1]["id"],
        }


def certificates():
    c = Certificate()
    h = c.assume(binary("and", P, Q))
    p = c.add("and_elim_left", conjunction=h)
    q = c.add("and_elim_right", conjunction=h)
    swapped = c.add("and_intro", left=q, right=p)
    forward = c.add("imp_intro", assumption=h, conclusion=swapped)
    k = c.assume(binary("and", Q, P))
    q = c.add("and_elim_left", conjunction=k)
    p = c.add("and_elim_right", conjunction=k)
    original = c.add("and_intro", left=p, right=q)
    backward = c.add("imp_intro", assumption=k, conclusion=original)
    c.add("iff_intro", left=forward, right=backward)
    yield ("and-commutes", "Conjunction in either order", "Both directions establish an equivalence, rather than only a necessary condition.", ["and", "iff"], c.finish(binary("iff", binary("and", P, Q), binary("and", Q, P))))

    c = Certificate()
    directions = []
    for a, b in ((P, Q), (Q, P)):
        h = c.assume(binary("or", a, b))
        ha = c.assume(a)
        target = c.add("or_intro_right", premise=ha, other=b)
        case_a = c.add("imp_intro", assumption=ha, conclusion=target)
        hb = c.assume(b)
        target = c.add("or_intro_left", premise=hb, other=a)
        case_b = c.add("imp_intro", assumption=hb, conclusion=target)
        result = c.add("or_elim", disjunction=h, left_case=case_a, right_case=case_b)
        directions.append(c.add("imp_intro", assumption=h, conclusion=result))
    c.add("iff_intro", left=directions[0], right=directions[1])
    yield ("or-commutes", "Disjunction by cases", "Each alternative reaches the same conclusion. OR alone never tells us which alternative holds.", ["or", "iff"], c.finish(binary("iff", binary("or", P, Q), binary("or", Q, P))))

    c = Certificate()
    source = binary("and", P, binary("implies", P, Q))
    h = c.assume(source)
    p = c.add("and_elim_left", conjunction=h)
    implication = c.add("and_elim_right", conjunction=h)
    result = c.add("imp_elim", implication=implication, antecedent=p)
    c.add("imp_intro", assumption=h, conclusion=result)
    yield ("modus-ponens", "Apply an implication", "If P implies Q and P holds, Q follows. The implication does not establish its converse.", ["and", "implies"], c.finish(binary("implies", source, Q)))

    c = Certificate()
    h = c.assume(binary("implies", P, Q))
    not_q = c.assume(neg(Q))
    p = c.assume(P)
    q = c.add("imp_elim", implication=h, antecedent=p)
    bottom = c.add("not_elim", positive=q, negative=not_q)
    not_p = c.add("not_intro", assumption=p, conclusion=bottom)
    conditional = c.add("imp_intro", assumption=not_q, conclusion=not_p)
    c.add("imp_intro", assumption=h, conclusion=conditional)
    yield ("modus-tollens", "Reason with a negated consequence", "Modus tollens is derived from implication and contradiction, with every assumption discharged explicitly.", ["not", "implies"], c.finish(binary("implies", binary("implies", P, Q), binary("implies", neg(Q), neg(P)))))

    c = Certificate()
    h = c.assume(neg(binary("or", P, Q)))
    negations = []
    for a, b, rule in ((P, Q, "or_intro_left"), (Q, P, "or_intro_right")):
        ha = c.assume(a)
        disjunction = c.add(rule, premise=ha, other=b)
        bottom = c.add("not_elim", positive=disjunction, negative=h)
        negations.append(c.add("not_intro", assumption=ha, conclusion=bottom))
    result = c.add("and_intro", left=negations[0], right=negations[1])
    c.add("imp_intro", assumption=h, conclusion=result)
    yield ("de-morgan", "Negation of a disjunction", "If neither alternative can hold, each individual alternative is false. This proof establishes the displayed direction.", ["not", "or", "and", "implies"], c.finish(binary("implies", neg(binary("or", P, Q)), binary("and", neg(P), neg(Q)))))

    c = Certificate()
    h = c.assume(binary("iff", P, Q))
    forward = c.add("iff_elim_left", equivalence=h)
    c.add("imp_intro", assumption=h, conclusion=forward)
    yield ("iff-forward", "Unpack an equivalence", "An explicitly supplied equivalence permits either implication. A single implication cannot introduce an equivalence.", ["iff", "implies"], c.finish(binary("implies", binary("iff", P, Q), binary("implies", P, Q))))


RULE_LABELS = {
    "assume": "Assumption", "and_intro": "AND introduction",
    "and_elim_left": "AND elimination · left", "and_elim_right": "AND elimination · right",
    "or_intro_left": "OR introduction · left", "or_intro_right": "OR introduction · right",
    "or_elim": "OR elimination · cases", "imp_intro": "Implication introduction",
    "imp_elim": "Modus ponens", "iff_intro": "IFF introduction · both directions",
    "iff_elim_left": "IFF elimination · forward", "iff_elim_right": "IFF elimination · backward",
    "not_intro": "NOT introduction · contradiction", "not_elim": "NOT elimination · contradiction",
    "bottom_elim": "Contradiction elimination",
}


def build_logical_reasoning():
    examples = []
    for identifier, title, explanation, operators, certificate in certificates():
        report = verify_propositional_proof(certificate)
        if not report["theorem_in_experimental_calculus"] or not report["semantic_truth_table_checked"]:
            raise ValueError("Concept-page schemas require a closed proof and an independent truth-table check")
        for step in report["steps"]:
            step["rule_label"] = RULE_LABELS[step["rule"]]
        examples.append({"id": identifier, "title": title, "explanation": explanation,
                         "operators": operators, "certificate": certificate, "verification": report})
    expressions = {"not_p": neg(P), "and": binary("and", P, Q), "or": binary("or", P, Q),
                   "implies": binary("implies", P, Q), "iff": binary("iff", P, Q)}
    table = [{"p": p, "q": q, **{name: _evaluate(formula, {"P": p, "Q": q})
              for name, formula in expressions.items()}} for p, q in product((False, True), repeat=2)]
    return {"contract_version": "logical-reasoning-preview@1", "scope": "Boolean propositional logic",
            "atom_meaning": "P and Q stand for arbitrary propositions, not recorded concept properties.",
            "canonical_knowledge_changed": False, "examples": examples, "truth_table": table}


if __name__ == "__main__":
    print(json.dumps(build_logical_reasoning(), ensure_ascii=False, sort_keys=True, indent=2))
