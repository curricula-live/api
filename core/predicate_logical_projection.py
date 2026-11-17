"""Translate actual admitted DB rows into scoped atoms and conditional deductions.

No synthetic concepts, absent-edge negation, class lifting or new canonical
assertions. Logical rules operate on the recorded assertions as premises.
"""
from collections import defaultdict
from copy import deepcopy

SYMBOLS = {
    'research_topic_parent_of': 'ResearchTopicParentOf',
    'adt_supports_operation': 'SupportsOperation',
    'adt_has_discipline': 'HasDiscipline',
    'logic_gate_implements_operation': 'ImplementsBooleanOperation',
    'value_of_type': 'ValueOfType',
}


def _join(labels):
    return labels[0] if len(labels) == 1 else ', '.join(labels[:-1]) + ' and ' + labels[-1]


def check_conclusion(conclusion, premises):
    """Check the exact premise IDs and computed AST, without trusting prose."""
    ids = conclusion['premise_ids']
    if not ids or len(set(ids)) != len(ids) or any(i not in premises for i in ids):
        raise ValueError('Unknown or duplicated logical premise')
    atoms = [premises[i]['expression'] for i in ids]
    if conclusion['rule'] == 'conjunction_introduction':
        if len(atoms) < 2:
            raise ValueError('Conjunction requires at least two premises')
        expected = {'op': 'and', 'args': atoms}
    elif conclusion['rule'] == 'existential_introduction':
        if len(atoms) != 1 or conclusion.get('quantified_argument') not in ('subject', 'object'):
            raise ValueError('Existential introduction requires one named witness')
        argument = conclusion['quantified_argument']
        if atoms[0][argument]['kind'] != 'concept':
            raise ValueError('Existential witness must be a recorded named endpoint')
        if conclusion.get('witness_concept_id') != atoms[0][argument]['id']:
            raise ValueError('Existential witness differs from the recorded endpoint')
        body = deepcopy(atoms[0])
        body[argument] = {'kind': 'variable', 'name': 'related'}
        expected = {'op': 'exists', 'variable': 'related', 'domain': 'named_knowledge_entities', 'body': body}
    else:
        raise ValueError('Unsupported logical consequence rule')
    if expected != conclusion['expression']:
        raise ValueError('Conclusion differs from the rule applied to its database premises')
    return True


def project_concept_admissions(concept_id, rows):
    premises = {}
    groups = defaultdict(list)
    unprojected = []
    for row in rows:
        policy = row['predicate_policy']
        logic = policy.get('logical_translation')
        predicate = row['predicate']
        evidence = row['evidence']
        if (not isinstance(logic, dict) or predicate not in SYMBOLS
                or logic.get('symbol') != SYMBOLS[predicate]
                or logic.get('form') != 'scoped_binary_relation' or logic.get('arity') != 2
                or any(logic.get(flag) is not False for flag in
                       ('class_subsumption', 'closed_world_negation', 'equivalence_from_edge'))
                or logic.get('allowed_conditional_rules') != ['conjunction_introduction', 'existential_introduction']
                or not evidence.get('original_source_assertion')):
            unprojected.append(row['statement_id'])
            continue
        if row['subject_concept_id'] == concept_id:
            direction = 'outgoing'
        elif row['object_concept_id'] == concept_id:
            direction = 'incoming'
        else:
            continue
        sid = row['statement_id']
        expression = {
            'op': 'scoped_relation', 'predicate': predicate, 'symbol': logic['symbol'],
            'scope': policy['semantic_scope'],
            'subject': {'kind': 'concept', 'id': row['subject_concept_id']},
            'object': {'kind': 'concept', 'id': row['object_concept_id']},
        }
        premise = {'statement_id': sid, 'expression': expression,
                   'source_assertion_witness': evidence['original_source_assertion']}
        if sid in premises:
            if premises[sid] != premise:
                raise ValueError('Conflicting duplicate statement identity')
            continue
        premises[sid] = premise
        groups[(predicate, policy['semantic_scope'], direction)].append(row)

    conclusions = []
    for (predicate, scope, direction), members in sorted(groups.items()):
        members.sort(key=lambda r: r['statement_id'])
        selected = members[:12]
        focus_key, other_key = ('subject', 'object') if direction == 'outgoing' else ('object', 'subject')
        focus = selected[0].get(focus_key + '_label') or concept_id
        others = [m.get(other_key + '_label') or m[other_key + '_concept_id'] for m in selected]
        if len(selected) > 1:
            if direction == 'outgoing':
                templates = {
                    'adt_supports_operation': f'{focus} supports {_join(others)}.',
                    'adt_has_discipline': f'{focus} has the recorded disciplines {_join(others)}.',
                    'logic_gate_implements_operation': f'{focus} implements {_join(others)} in the recorded Boolean scope.',
                    'value_of_type': f'{focus} is recorded as a value of {_join(others)}.',
                    'research_topic_parent_of': f'{focus} has {_join(others)} as directly recorded narrower research topics.',
                }
            else:
                templates = {
                    'value_of_type': f'{focus} has recorded values {_join(others)}.',
                    'adt_supports_operation': f'{focus} is supported by {_join(others)}.',
                    'adt_has_discipline': f'{focus} is a recorded discipline of {_join(others)}.',
                    'logic_gate_implements_operation': f'{focus} is implemented by {_join(others)} in the recorded Boolean scope.',
                    'research_topic_parent_of': f'{focus} is directly organized under {_join(others)} as a research topic.',
                }
            conclusions.append({
                'rule': 'conjunction_introduction', 'text': templates[predicate],
                'expression': {'op': 'and', 'args': [premises[m['statement_id']]['expression'] for m in selected]},
                'premise_ids': [m['statement_id'] for m in selected],
                'covers_retrieved_group': len(members) <= 12,
            })
        # Existential introduction uses an actual endpoint as its witness;
        # never infer exact counts or a universal statement from these edges.
        witness = selected[0]
        body = deepcopy(premises[witness['statement_id']]['expression'])
        body[other_key] = {'kind': 'variable', 'name': 'related'}
        outgoing = {
            'adt_supports_operation': f'{focus} supports at least one operation.',
            'adt_has_discipline': f'{focus} has at least one recorded ordering discipline.',
            'logic_gate_implements_operation': f'{focus} implements at least one Boolean operation.',
            'value_of_type': f'{focus} is a recorded value of at least one type.',
            'research_topic_parent_of': f'{focus} has at least one directly recorded narrower research topic.',
        }
        incoming = {
            'value_of_type': f'At least one recorded value belongs to {focus}.',
            'adt_supports_operation': f'At least one abstract data type supports {focus}.',
            'adt_has_discipline': f'At least one abstract data type has the recorded discipline {focus}.',
            'logic_gate_implements_operation': f'At least one named gate implements {focus} in the recorded Boolean scope.',
            'research_topic_parent_of': f'{focus} has at least one directly recorded broader research topic.',
        }
        conclusions.append({
            'rule': 'existential_introduction', 'text': (outgoing if direction == 'outgoing' else incoming)[predicate],
            'expression': {'op': 'exists', 'variable': 'related', 'domain': 'named_knowledge_entities', 'body': body},
            'premise_ids': [witness['statement_id']], 'quantified_argument': other_key,
            'witness_concept_id': witness[other_key + '_concept_id'],
        })
    for conclusion in conclusions:
        conclusion['rule_application_checked'] = check_conclusion(conclusion, premises)
        conclusion['status'] = 'conditional_on_recorded_source_assertions'
        conclusion['canonical_claim_approved'] = False
        conclusion['scientific_truth_verified'] = False
    return {'contract_version': 'predicate-logical-projection@1',
            'premises': list(premises.values()), 'conclusions': conclusions,
            'unprojected_statement_ids': unprojected,
            'scope': 'retrieved_database_assertions_only'}
