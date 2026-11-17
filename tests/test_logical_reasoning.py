from copy import deepcopy

import pytest

from core.formal_propositional_proofs import PropositionalProofError, verify_propositional_proof
from core.logical_reasoning import Certificate, P, Q, R, binary, neg, build_logical_reasoning, certificates


def test_all_published_schemas_are_closed_and_truth_table_checked():
    artifact = build_logical_reasoning()
    assert len(artifact['examples']) == 6
    for example in artifact['examples']:
        report = example['verification']
        assert report['logical_rules_checked'] and report['semantic_truth_table_checked']
        assert report['theorem_in_experimental_calculus']
        assert report['open_assumption_step_ids'] == []
        assert not report['canonical_claim_approved']
        assert not report['scientific_sources_verified']
        assert report['conclusion_step_id'] == report['steps'][-1]['id']
    assert artifact == build_logical_reasoning()
    assert artifact['truth_table'][-1] == {
        'p': True, 'q': True, 'not_p': False, 'and': True, 'or': True, 'implies': True, 'iff': True}


def test_cases_cannot_ignore_or_swap_an_alternative():
    cert = next(item[-1] for item in certificates() if item[0] == 'or-commutes')
    step = next(s for s in cert['steps'] if s['rule'] == 'or_elim')
    step['right_case'] = step['left_case']
    with pytest.raises(PropositionalProofError, match='both alternatives'):
        verify_propositional_proof(cert)


def test_not_elimination_needs_exact_negation():
    c = Certificate()
    p = c.assume(P)
    not_q = c.assume(neg(Q))
    c.add('not_elim', positive=p, negative=not_q)
    with pytest.raises(PropositionalProofError, match='proposition and its negation'):
        verify_propositional_proof(c.finish({'op': 'bottom'}))


def test_not_introduction_cannot_discharge_without_contradiction():
    c = Certificate()
    p = c.assume(P)
    q = c.assume(Q)
    c.add('not_intro', assumption=p, conclusion=q)
    with pytest.raises(PropositionalProofError, match='assumption and contradiction'):
        verify_propositional_proof(c.finish(neg(P)))


def test_contradiction_elimination_preserves_both_open_assumptions():
    c = Certificate()
    p = c.assume(P)
    not_p = c.assume(neg(P))
    bottom = c.add('not_elim', positive=p, negative=not_p)
    c.add('bottom_elim', contradiction=bottom, formula=R)
    report = verify_propositional_proof(c.finish(R))
    assert report['open_assumption_step_ids'] == [p, not_p]
    assert not report['theorem_in_experimental_calculus']


def test_no_explosion_without_bottom():
    c = Certificate()
    p = c.assume(P)
    c.add('bottom_elim', contradiction=p, formula=Q)
    with pytest.raises(PropositionalProofError, match='explicit contradiction'):
        verify_propositional_proof(c.finish(Q))


def test_de_morgan_discharge_keeps_outer_assumption_until_implication():
    cert = next(item[-1] for item in certificates() if item[0] == 'de-morgan')
    report = verify_propositional_proof(cert)
    negations = [s for s in report['steps'] if s['rule'] == 'not_intro']
    assert len(negations) == 2
    assert all(s['open_assumption_step_ids'] == ['s1'] for s in negations)
    assert all(s['discharged_assumption_step_id'] for s in negations)
    assert report['steps'][-1]['open_assumption_step_ids'] == []
