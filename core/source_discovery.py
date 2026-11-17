"""Opt-in, read-only access to staged SOURCE records, never canonical facts.

The source graph contains unreviewed identity candidates, taxonomy and metadata.
Neither type subsumption nor prerequisites may be derived from these records.
"""
from django.conf import settings
from django.db import connection, OperationalError, ProgrammingError
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET

SOURCES=("cso@3.5","curricula-historical-v1@1.0.0")

def allowed():
    if settings.IS_PRODUCTION or not getattr(settings,"V2_READ_PREVIEW_ENABLED",False):
        raise Http404("Source preview unavailable")

def pagination(request, max_limit=100):
    try:
        limit=int(request.GET.get("limit","30"))
        offset=int(request.GET.get("offset","0"))
    except (ValueError,TypeError):
        return None
    return (limit,offset) if 1<=limit<=max_limit and 0<=offset<=10000 else None

def unavailable():
    return JsonResponse({"error":"source review database unavailable"},status=503,
                        headers={"Cache-Control":"no-store"})

def response(payload):
    return JsonResponse({
        "contract_version":"source-discovery-preview@1",
        "source_review_verified":False,
        "canonical_identity_approved":False,
        "inference_eligible":False,
        "provisional":True,
        **payload,
    },headers={"Cache-Control":"no-store"})

@require_GET
def source_search(request):
    allowed()
    page=pagination(request)
    q=request.GET.get("q","").strip()
    if page is None or not 2<=len(q)<=100 or any(ord(c)<32 for c in q):
        return JsonResponse({"error":"invalid query or pagination"},status=400)
    limit,offset=page
    pattern="%"+q.replace("\\","\\\\").replace("%","\\%").replace("_","\\_")+"%"
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                select source_id,source_uri,label,canonical_candidate_ids,identity_review_status
                from knowledge_source.topic
                where label ilike %s
                order by case when lower(label)=lower(%s) then 0
                              when lower(label) like lower(%s) then 1 else 2 end,
                         length(label),label,source_id,source_uri
                limit %s offset %s
            """,[pattern,q,q.replace("\\","\\\\").replace("%","\\%").replace("_","\\_")+"%",limit+1,offset])
            rows=cursor.fetchall()
    except (ProgrammingError,OperationalError):
        return unavailable()
    return response({"query":q,"limit":limit,"offset":offset,"has_more":len(rows)>limit,
        "results":[{"source_id":a,"source_uri":b,"label":c,
                    "canonical_candidate_ids":[str(x) for x in d],
                    "identity_review_status":e,"status":"unreviewed_source_topic"}
                   for a,b,c,d,e in rows[:limit]]})

@require_GET
def source_relations(request):
    allowed()
    page=pagination(request)
    source_id=request.GET.get("source_id","").strip()
    uri=request.GET.get("source_uri","").strip()
    if (page is None or source_id not in SOURCES or not 1<=len(uri)<=500
            or not uri.startswith(("http://","https://")) or any(ord(x)<32 for x in uri)):
        return JsonResponse({"error":"invalid source, URI or pagination"},status=400)
    limit,offset=page
    try:
        with connection.cursor() as cursor:
            cursor.execute("select source_id,source_uri,label from knowledge_source.topic where source_id=%s and source_uri=%s",[source_id,uri])
            topic=cursor.fetchone()
            if topic is None:
                raise Http404("Unknown source topic")
            cursor.execute("""
                select source_assertion_witness,subject_uri,native_predicate,object_uri,
                       subject_candidate_ids,object_candidate_ids,reconciliation_status
                  from knowledge_source.assertion
                 where source_id=%s and (subject_uri=%s or object_uri=%s)
                 order by source_assertion_witness
                 limit %s offset %s
            """,[source_id,uri,uri,limit+1,offset])
            rows=cursor.fetchall()
    except (ProgrammingError,OperationalError):
        return unavailable()
    return response({"topic":{"source_id":topic[0],"source_uri":topic[1],"label":topic[2]},
        "limit":limit,"offset":offset,"has_more":len(rows)>limit,
        "relations":[{"source_assertion_witness":a,"subject_uri":b,
                      "native_predicate":c,"object_uri":d,
                      "subject_candidate_ids":[str(x) for x in e],
                      "object_candidate_ids":[str(x) for x in f],
                      "reconciliation_status":g,
                      "direction":"outgoing" if b==uri else "incoming",
                      "inference_eligible":False,"review_status":"unreviewed_source_relation"}
                     for a,b,c,d,e,f,g in rows[:limit]]})

@require_GET
def source_predicates(request):
    allowed()
    source_id=request.GET.get("source_id","").strip()
    if source_id not in SOURCES:
        return JsonResponse({"error":"unknown source"},status=400)
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                select native_predicate,proposed_slug,semantic_family,review_status
                from knowledge_source.predicate
                where source_id=%s order by native_predicate limit 32
            """,[source_id])
            rows=cursor.fetchall()
    except (ProgrammingError,OperationalError):
        return unavailable()
    return response({"source_id":source_id,"predicates":[
        {"native_predicate":a,"proposed_slug":b,"semantic_family":c,
         "review_status":d,"inference_eligible":False} for a,b,c,d in rows]})
