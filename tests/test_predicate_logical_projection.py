from copy import deepcopy
import pytest
from core.predicate_logical_projection import project_concept_admissions, check_conclusion


def row(sid, subject, obj, subject_label, object_label, predicate='adt_supports_operation', symbol='SupportsOperation', scope='abstract_data_type_interface'):
    return {'statement_id':sid,'subject_concept_id':subject,'object_concept_id':obj,
        'subject_label':subject_label,'object_label':object_label,'predicate':predicate,
        'predicate_policy':{'semantic_scope':scope,'logical_translation':{
            'symbol':symbol,'form':'scoped_binary_relation','arity':2,
            'allowed_conditional_rules':['conjunction_introduction','existential_introduction'],
            'class_subsumption':False,'closed_world_negation':False,'equivalence_from_edge':False}},
        'evidence':{'original_source_assertion':'source:'+sid}}


def test_real_subjects_and_exact_premises_are_conjoined_without_hand_authored_conclusions():
    rows=[row('statement-pop','stack','pop','Stack ADT','Stack pop'),
          row('statement-push','stack','push','Stack ADT','Stack push')]
    result=project_concept_admissions('stack',rows)
    combined=next(c for c in result['conclusions'] if c['rule']=='conjunction_introduction')
    assert combined['text']=='Stack ADT supports Stack pop and Stack push.'
    assert combined['premise_ids']==['statement-pop','statement-push']
    assert combined['expression']['op']=='and'
    assert all(a['subject']['id']=='stack' for a in combined['expression']['args'])
    changed=project_concept_admissions('queue',[row('one','queue','enqueue','Queue ADT','Queue enqueue')])
    assert len(changed['conclusions'])==1
    assert changed['conclusions'][0]['text']=='Queue ADT supports at least one operation.'
    assert 'Stack' not in str(changed)


def test_incoming_value_membership_is_not_class_subsumption():
    rows=[row('false-value','false','boolean','Boolean false','Boolean type','value_of_type','ValueOfType','two_valued_boolean_or_binary_digit')]
    result=project_concept_admissions('boolean',rows)
    c=result['conclusions'][0]
    assert c['quantified_argument']=='subject'
    assert c['witness_concept_id']=='false'
    assert c['expression']['body']['object']['id']=='boolean'
    assert c['expression']['body']['subject']['kind']=='variable'
    assert c['text']=='At least one recorded value belongs to Boolean type.'
    assert 'subsumption' not in str(c['expression'])


def test_cso_is_direct_topic_relation_not_subtype_transitivity():
    rows=[row('a','cs','ai','Computer science','Artificial intelligence','research_topic_parent_of','ResearchTopicParentOf','research_topic_direct_organizational_hierarchy'),
          row('b','ai','ml','Artificial intelligence','Machine learning','research_topic_parent_of','ResearchTopicParentOf','research_topic_direct_organizational_hierarchy')]
    result=project_concept_admissions('cs',rows)
    assert len(result['premises'])==1
    assert all(c['rule']=='existential_introduction' for c in result['conclusions'])
    assert 'ml' not in str(result)


@pytest.mark.parametrize('mutation',['missing','symbol','upgrade'])
def test_unknown_or_stronger_semantics_do_not_produce_logical_facts(mutation):
    r=row('one','stack','pop','Stack ADT','Stack pop')
    if mutation=='missing': r['predicate_policy']['logical_translation']=None
    elif mutation=='symbol': r['predicate_policy']['logical_translation']['symbol']='SubtypeOf'
    else: r['predicate_policy']['logical_translation']['class_subsumption']=True
    result=project_concept_admissions('stack',[r])
    assert result['premises']==[] and result['conclusions']==[]
    assert result['unprojected_statement_ids']==['one']


def test_different_semantic_scopes_are_not_merged():
    result=project_concept_admissions('stack',[row('a','stack','pop','Stack ADT','Stack pop'),row('b','stack','push','Stack ADT','Stack push',scope='different_scope')])
    assert all(c['rule']=='existential_introduction' for c in result['conclusions'])


def test_checker_rejects_invented_premise_or_changed_conclusion_or_fake_witness():
    result=project_concept_admissions('stack',[row('a','stack','pop','Stack ADT','Stack pop')])
    premises={p['statement_id']:p for p in result['premises']}
    c=deepcopy(result['conclusions'][0]);c['premise_ids']=['missing']
    with pytest.raises(ValueError,match='Unknown'):check_conclusion(c,premises)
    c=deepcopy(result['conclusions'][0]);c['expression']['body']['scope']='different'
    with pytest.raises(ValueError,match='differs'):check_conclusion(c,premises)
    c=deepcopy(result['conclusions'][0]);c['witness_concept_id']='invented'
    with pytest.raises(ValueError,match='witness differs'):check_conclusion(c,premises)


def test_no_database_premises_means_no_generated_conclusions():
    assert project_concept_admissions('stack',[])['conclusions']==[]
