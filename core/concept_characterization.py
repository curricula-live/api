"""Evidence-linked characterizations of both ends of recorded relations.

Inverse readings change the sentence viewpoint, never the stored predicate,
its direction, or its logical eligibility. Topic-source edges are excluded.
"""
OUTGOING = {
    'subtype_of': 'is a kind of',
    'adt_supports_operation': 'supports the operations',
    'adt_has_discipline': 'follows the discipline',
    'logic_gate_implements_operation': 'implements the Boolean operation',
    'value_of_type': 'is a value of',
    'uses': 'uses', 'processes': 'processes', 'produces': 'produces',
    'stores': 'stores', 'transmits': 'transmits', 'represents': 'represents',
    'implemented_by': 'is implemented by', 'part_of': 'is part of',
    'encodes': 'encodes', 'executes': 'executes', 'measures': 'measures',
    'identifies': 'identifies', 'protects': 'protects',
    'protects_against': 'protects against', 'property_of': 'is a property of',
    'research_topic_parent_of': 'has the directly recorded narrower research topics',
}
INCOMING = {
    'subtype_of': 'has recorded subtypes including',
    'adt_supports_operation': 'is an operation supported by',
    'adt_has_discipline': 'is a discipline followed by',
    'logic_gate_implements_operation': 'is the Boolean operation implemented by',
    'value_of_type': 'has recorded values including',
    'uses': 'is used by', 'processes': 'is processed by',
    'produces': 'is produced by', 'stores': 'is stored by',
    'transmits': 'is transmitted by', 'represents': 'is represented by',
    'implemented_by': 'implements', 'part_of': 'has recorded parts including',
    'encodes': 'is encoded by', 'executes': 'is executed by',
    'measures': 'is measured by', 'identifies': 'is identified by',
    'protects': 'is protected by', 'protects_against': 'is protected against by',
    'property_of': 'has recorded properties including',
    'research_topic_parent_of': 'is directly organized under the research topics',
}


def _join(names):
    return names[0] if len(names) == 1 else ', '.join(names[:-1]) + ' and ' + names[-1]


def build_characterization(slug, label, labels, edges, derived=(), *, truncated=False):
    clauses = []
    for direction, phrases, focus, other in (
        ('outgoing', OUTGOING, 'source', 'target'),
        ('incoming', INCOMING, 'target', 'source'),
    ):
        for predicate, phrase in phrases.items():
            group = sorted(
                (e for e in edges if not e.get('source_only', False)
                 and e[focus] == slug and e[other] != slug and e['predicate'] == predicate),
                key=lambda e: (e[other], e['id']),
            )
            selected = group[:6]
            if not selected:
                continue
            names = [labels.get(e[other], e[other]) for e in selected]
            clauses.append({
                'text': f'{label if not clauses else "It"} {phrase} {_join(names)}.',
                'direction': direction, 'predicate': predicate,
                'basis': 'recorded_assertions',
                'assertion_ids': [e['id'] for e in selected],
                'group_truncated': len(group) > len(selected),
            })
    available = {e['id'] for e in edges if not e.get('source_only', False)}
    for d in sorted(derived, key=lambda d: d['target'])[:4]:
        if (d.get('rule') != 'subtype_of_transitivity' or d.get('subject') != slug
                or not d.get('proof', {}).get('rule_application_checked')
                or not d['premise_ids'] or not set(d['premise_ids']) <= available):
            continue
        clauses.append({
            'text': f'By recorded subtype transitivity, {label} is also a kind of {labels.get(d["target"], d["target"])}.',
            'direction': 'outgoing', 'predicate': 'subtype_of',
            'basis': 'conditional_inference', 'rule': d['rule'],
            'assertion_ids': d['premise_ids'], 'group_truncated': False,
        })
    if not clauses:
        return None
    return {
        'text': ' '.join(c['text'] for c in clauses),
        'assertion_ids': list(dict.fromkeys(i for c in clauses for i in c['assertion_ids'])),
        'clauses': clauses, 'status': 'provisional_knowledge_v2',
        'method': 'bidirectional_recorded_relations_with_conditional_subtypes',
        'retrieval_truncated': truncated,
        'equivalence_established': False,
    }
