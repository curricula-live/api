import uuid
from core.staging_concepts import read_neighborhood, REASONING_DEPTH
from core.concept_documentation import _derive_subtypes


def uid(name):
    return uuid.uuid5(uuid.NAMESPACE_URL, name)


class Cursor:
    def execute(self, query, params):
        frontier = set(params[0])
        source = 'knowledge_source.assertion' in query
        rows = []
        if source:
            for i in range(200):
                if uid('n0') in frontier or uid(f'hub-{i}') in frontier:
                    rows.append((f'witness-{i}', uid('n0'), 'n0', 'N0', 'broaderTopic', uid(f'hub-{i}'), f'hub-{i}', f'Hub {i}'))
        else:
            for i in range(5):
                a,b=uid(f'n{i}'),uid(f'n{i+1}')
                if (a in frontier or b in frontier) and (not params[2] or a in frontier):
                    rows.append((uid(f'edge-{i}'),a,f'n{i}',f'N{i}','subtype_of',b,f'n{i+1}',f'N{i+1}'))
        self.rows=rows[:params[-1]]

    def fetchall(self):
        return self.rows


def test_source_hub_does_not_consume_the_reasoning_path_budget():
    nodes,edges,truncated=read_neighborhood(Cursor(), (uid('n0'),'n0','N0'), REASONING_DEPTH)
    canonical=[e for e in edges if not e['source_only']]
    conclusion=next(d for d in _derive_subtypes('n0',canonical,5) if d['target']=='n5')
    assert len(conclusion['premise_ids']) == 5
    assert len(canonical) == 5
    assert truncated  # The source neighborhood was bounded, the proof survived.
    assert len([n for n in nodes if n['slug'].startswith('hub-')]) <= 119
