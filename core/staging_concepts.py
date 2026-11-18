"""Development-only concept pages over the real canonical/source PostgreSQL tables."""
from collections import defaultdict
import json
import uuid
from django.conf import settings
from django.db import connection, OperationalError, ProgrammingError
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET
from core.concept_documentation import _derive_subtypes
from core.concept_characterization import build_characterization
from core.concept_formal_expressions import direct_class_conditions
from core.concept_relation_profile import build_relation_profile
from core.predicate_logical_projection import project_concept_admissions

STATUS = 'provisional_knowledge_v2'
MAX_NODES, MAX_EDGES = 120, 240


def guard():
    if settings.IS_PRODUCTION or not getattr(settings, 'V2_READ_PREVIEW_ENABLED', False):
        raise Http404('Development knowledge unavailable')


def respond(reader):
    guard()
    try:
        with connection.cursor() as cursor:
            result = reader(cursor)
    except (OperationalError, ProgrammingError):
        return JsonResponse({'error':'development knowledge unavailable'},status=503)
    return JsonResponse(result,headers={'Cache-Control':'no-store'})


def concept_row(cursor, slug):
    cursor.execute('select id,slug,label from knowledge.concept where slug=%s',[slug])
    row=cursor.fetchone()
    if row is None: raise Http404('Unknown concept')
    return row


def _json(value):
    return json.loads(value) if isinstance(value,str) else value


def text(subject,predicate,obj):
    phrases={
      'subtype_of':'is a kind of','part_of':'is part of','uses':'uses',
      'processes':'processes','produces':'produces','stores':'stores',
      'transmits':'transmits','represents':'represents','implemented_by':'is implemented by',
      'adt_supports_operation':'supports','adt_has_discipline':'follows',
      'logic_gate_implements_operation':'implements the Boolean operation',
      'value_of_type':'is a value of',
      'research_topic_parent_of':'has the directly recorded narrower research topic',
      'source_broader_topic':'has the recorded broader source topic',
      'source_subtopic_of':'is recorded as a source subtopic of',
    }
    return f'{subject} {phrases.get(predicate,predicate.replace("_"," "))} {obj}.'


@require_GET
def search(request):
    q=request.GET.get('q','').strip()
    category=request.GET.get('category','all')
    if len(q)>100 or category not in ('all','concepts','connections'):
        return JsonResponse({'error':'invalid search'},status=400)
    def read(cursor):
        escaped=q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        pattern='%'+escaped+'%'
        concepts=[]; relations=[]
        if category!='connections':
            cursor.execute('''select id,slug,label from knowledge.concept
                where label ilike %s or slug ilike %s
                order by case when lower(label)=lower(%s) or lower(slug)=lower(%s) then 0 else 1 end,
                         length(label),label,slug limit 100''',[pattern,pattern,q,q])
            concepts=[{'id':str(i),'slug':s,'label':l} for i,s,l in cursor.fetchall()]
        if category!='concepts':
            cursor.execute('''select s.id,a.slug,s.predicate_slug,b.slug
                from knowledge.statement s join knowledge.concept a on a.id=s.subject_concept_id
                join knowledge.concept b on b.id=s.object_concept_id
                where a.label ilike %s or b.label ilike %s order by s.id limit 100''',[pattern,pattern])
            relations=[{'id':str(i),'source':a,'type':p,'target':b} for i,a,p,b in cursor.fetchall()]
        return {'query':q,'results':{'concepts':concepts,'connections':relations},'data_source':'staging-knowledge-database'}
    return respond(read)


@require_GET
def directory(request):
    def read(cursor):
        cursor.execute('select id,slug,label from knowledge.concept order by slug limit 10000')
        return {'results':[{'id':str(i),'slug':s,'label':l} for i,s,l in cursor.fetchall()]}
    return respond(read)


@require_GET
def detail(request,slug):
    def read(cursor):
        i,s,l=concept_row(cursor,slug)
        return {'id':str(i),'slug':s,'label':l,'status':STATUS}
    return respond(read)


def read_neighborhood(cursor,root,depth):
    nodes={str(root[0]):{'id':str(root[0]),'slug':root[1],'label':root[2],'hop':0}}
    frontier=[root[0]]; edges={}; truncated=False
    for hop in range(1,depth+1):
        if not frontier or len(edges)>=MAX_EDGES:break
        cursor.execute('''select s.id,a.id,a.slug,a.label,s.predicate_slug,b.id,b.slug,b.label
          from knowledge.statement s join knowledge.concept a on a.id=s.subject_concept_id
          join knowledge.concept b on b.id=s.object_concept_id
          where a.id=any(%s::uuid[]) or b.id=any(%s::uuid[])
          order by case when s.predicate_slug='subtype_of' then 0 else 1 end,s.id limit 241''',[frontier,frontier])
        rows=[(str(i),a,sa,la,p,b,sb,lb,False,None) for i,a,sa,la,p,b,sb,lb in cursor.fetchall()]
        # Native historical topic edges are shown as source records only. They
        # never enter canonical subtype or admitted-predicate inference.
        cursor.execute('''select r.source_assertion_witness,a.id,a.slug,a.label,r.native_predicate,b.id,b.slug,b.label
          from knowledge_source.assertion r
          join knowledge.concept a on a.id=r.subject_candidate_ids[1]
          join knowledge.concept b on b.id=r.object_candidate_ids[1]
          where r.source_id='curricula-historical-v1@1.0.0'
            and cardinality(r.subject_candidate_ids)=1 and cardinality(r.object_candidate_ids)=1
            and r.native_predicate in ('broaderTopic','subtopicOf')
            and (a.id=any(%s::uuid[]) or b.id=any(%s::uuid[]))
          order by r.source_assertion_witness limit 241''',[frontier,frontier])
        for witness,a,sa,la,p,b,sb,lb in cursor.fetchall():
            rows.append((str(uuid.uuid5(uuid.NAMESPACE_URL,'curricula-source-witness:'+witness)),a,sa,la,
                         'source_broader_topic' if p=='broaderTopic' else 'source_subtopic_of',b,sb,lb,True,witness))
        if len(rows)>MAX_EDGES:truncated=True
        next_frontier=[]
        for sid,a,sa,la,p,b,sb,lb,source_only,witness in rows:
            if sid in edges:continue
            if len(edges)>=MAX_EDGES:truncated=True;break
            if any(str(i) not in nodes for i in (a,b)) and len(nodes)>=MAX_NODES:
                truncated=True;continue
            for i,s,l in ((a,sa,la),(b,sb,lb)):
                key=str(i)
                if key not in nodes:
                    if len(nodes)>=MAX_NODES:truncated=True;break
                    nodes[key]={'id':key,'slug':s,'label':l,'hop':hop};next_frontier.append(i)
            if str(a) not in nodes or str(b) not in nodes:continue
            edges[sid]={'id':sid,'source':sa,'predicate':p,'target':sb,'text':text(la,p,lb),
                'hop':max(nodes[str(a)]['hop'],nodes[str(b)]['hop']),
                'status':'source_recorded_not_canonical' if source_only else STATUS,
                'source_assertion_witness':witness,'source_only':source_only}
        frontier=next_frontier
    return list(nodes.values()), sorted(edges.values(),key=lambda e:(e['hop'],e['source'],e['predicate'],e['target'],e['id'])), truncated


def admitted_projection(cursor,root):
    cursor.execute('''select s.id,s.subject_concept_id,s.predicate_slug,s.object_concept_id,a.review_record,p.policy_record
        from knowledge.statement s join knowledge.statement_admission a on a.statement_id=s.id
        join knowledge.predicate_semantic_policy p on p.predicate_slug=s.predicate_slug
        where s.subject_concept_id=%s or s.object_concept_id=%s order by s.id limit 100''',[root[0],root[0]])
    rows=[]
    for sid,subject,predicate,obj,review,policy in cursor.fetchall():
        review=_json(review);policy=_json(policy)
        rows.append({'statement_id':str(sid),'subject_concept_id':str(subject),'object_concept_id':str(obj),
          'subject_label':review['subject_label'],'object_label':review['object_label'],'predicate':predicate,
          'predicate_policy':{'semantic_scope':policy['semantic_scope'],'logical_translation':policy.get('logical_translation')},
          'evidence':{'original_source_assertion':review['source_assertion_witness']}})
    return project_concept_admissions(str(root[0]),rows)


@require_GET
def documentation(request,slug):
    try:depth=int(request.GET.get('depth','2'))
    except ValueError:return JsonResponse({'error':'invalid depth'},status=400)
    if not 1<=depth<=5:return JsonResponse({'error':'invalid depth'},status=400)
    def read(cursor):
        root=concept_row(cursor,slug)
        nodes,edges,truncated=read_neighborhood(cursor,root,depth)
        canonical=[e for e in edges if not e['source_only']]
        derived=_derive_subtypes(slug,canonical,depth)
        labels={n['slug']:n['label'] for n in nodes}
        for d in derived:d['text']=text(labels.get(slug,slug),'subtype_of',labels.get(d['target'],d['target']))
        characterization=build_characterization(slug,root[2],labels,canonical,derived,truncated=truncated)
        projection=admitted_projection(cursor,root)
        available={e['id'] for e in edges}
        scoped=[c for c in projection['conclusions'] if set(c['premise_ids'])<=available]
        return {
          'contract_version':'legacy-concept-documentation@1','concept':{'slug':slug,'label':root[2]},
          'source':{'kind':'canonical_staging_statements','status':STATUS,'is_published_v2':False,'is_peer_reviewed':False,
                    'description':'Database-backed development corpus with scoped source records and conditional inference.'},
          'traversal':{'depth':depth,'max_depth':5,'max_nodes':MAX_NODES,'max_edges':MAX_EDGES,'truncated':truncated},
          'graph':{'nodes':nodes,'edges':edges},
          'characterization':characterization,
          'class_conditions':direct_class_conditions(slug,canonical),'asserted_statements':edges,
          'derived_statements':derived,'scoped_derivations':scoped,
          'relation_profile':build_relation_profile(slug,edges,derived,truncated=truncated),
          'derivation_policy':{'implemented_rules':['subtype_of_transitivity','conjunction_introduction','existential_introduction'],
              'rule_description':'Rules apply only to their supported database premises.','conditional_on_premises':True,
              'is_formal_proof_certificate':False,'uses_implies_prerequisite':False,'uses_implies_indexed_access':False},
        }
    return respond(read)


@require_GET
def neighborhood(request,slug):
    def read(cursor):
        root=concept_row(cursor,slug)
        _,edges,_=read_neighborhood(cursor,root,1)
        def payload(e):return {'id':e['id'],'source':e['source'],'type':e['predicate'],'target':e['target']}
        return {'concept':{'slug':slug},'outgoing':[payload(e) for e in edges if e['source']==slug],
                'incoming':[payload(e) for e in edges if e['target']==slug]}
    return respond(read)
