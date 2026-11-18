from core.concept_characterization import build_characterization
from core.concept_documentation import _derive_subtypes


def edge(i, a, p, b, **kwargs):
    return dict(id=i, source=a, predicate=p, target=b, **kwargs)


def test_incoming_operation_preserves_original_direction_and_evidence():
    rows = [edge('interface', 'stack-adt', 'adt_supports_operation', 'stack-pop')]
    result = build_characterization('stack-pop', 'Stack pop', {'stack-adt': 'Stack ADT'}, rows)
    assert result['text'] == 'Stack pop is an operation supported by Stack ADT.'
    assert result['clauses'][0]['direction'] == 'incoming'
    assert result['assertion_ids'] == ['interface']
    assert rows[0]['source'] == 'stack-adt'


def test_combines_class_actions_and_incoming_roles_without_sibling_leakage():
    rows = [edge('class', 'pop', 'subtype_of', 'operation'),
            edge('use', 'algorithm', 'uses', 'pop'),
            edge('produce', 'pop', 'produces', 'value'),
            edge('sibling', 'other', 'uses', 'value')]
    result = build_characterization('pop', 'Pop', {'operation': 'Operation', 'algorithm': 'Algorithm', 'value': 'Value'}, rows)
    assert result['text'] == 'Pop is a kind of Operation. It produces Value. It is used by Algorithm.'
    assert result['assertion_ids'] == ['class', 'produce', 'use']
    assert result['equivalence_established'] is False


def test_incoming_subtype_and_implementation_are_not_reversed():
    rows = [edge('sub', 'child', 'subtype_of', 'parent'),
            edge('impl', 'spec', 'implemented_by', 'parent')]
    result = build_characterization('parent', 'Parent', {'child': 'Child', 'spec': 'Specification'}, rows)
    assert 'has recorded subtypes including Child' in result['text']
    assert 'implements Specification' in result['text']
    assert 'kind of Child' not in result['text']


def test_unknown_and_source_only_edges_do_not_define_the_focus():
    rows = [edge('raw', 'x', 'subtype_of', 'parent', source_only=True),
            edge('topic', 'x', 'source_broader_topic', 'topic'),
            edge('unknown', 'other', 'unreviewed', 'x')]
    assert build_characterization('x', 'X', {}, rows) is None


def test_derived_characterization_requires_checked_available_premises():
    rows = [edge('a', 'file-read', 'subtype_of', 'file-operation'),
            edge('b', 'file-operation', 'subtype_of', 'computational-operation')]
    derived = _derive_subtypes('file-read', rows, 2)
    result = build_characterization('file-read', 'File read', {}, rows, derived)
    clause = result['clauses'][-1]
    assert clause['basis'] == 'conditional_inference'
    assert clause['assertion_ids'] == ['a', 'b']
    assert 'By recorded subtype transitivity' in clause['text']
    derived[0]['premise_ids'] = ['missing']
    result = build_characterization('file-read', 'File read', {}, rows, derived)
    assert all(c['basis'] == 'recorded_assertions' for c in result['clauses'])


def test_large_incoming_groups_are_bounded_and_identify_their_partial_scope():
    rows = [edge(str(i), f'user-{i}', 'uses', 'x') for i in range(10)]
    result = build_characterization('x', 'X', {}, rows, truncated=True)
    assert len(result['assertion_ids']) == 6
    assert result['clauses'][0]['group_truncated']
    assert result['retrieval_truncated']


def test_preview_documentation_includes_incoming_only_characterization(monkeypatch):
    import json
    from django.test import RequestFactory
    from core import staging_concepts
    monkeypatch.setattr(staging_concepts, 'respond', lambda read: __import__('django.http', fromlist=['JsonResponse']).JsonResponse(read(None)))
    monkeypatch.setattr(staging_concepts, 'concept_row', lambda cursor, slug: ('pop-id', slug, 'Stack pop'))
    rows = [edge('supports', 'stack-adt', 'adt_supports_operation', 'stack-pop', source_only=False, hop=1)]
    nodes = [{'slug': 'stack-pop', 'label': 'Stack pop', 'hop': 0}, {'slug': 'stack-adt', 'label': 'Stack ADT', 'hop': 1}]
    monkeypatch.setattr(staging_concepts, 'read_neighborhood', lambda *args: (nodes, rows, False))
    monkeypatch.setattr(staging_concepts, 'admitted_projection', lambda *args: {'conclusions': []})
    response = staging_concepts.documentation(RequestFactory().get('/'), 'stack-pop')
    result = json.loads(response.content)
    assert result['characterization']['text'] == 'Stack pop is an operation supported by Stack ADT.'
    assert result['characterization']['assertion_ids'] == ['supports']
