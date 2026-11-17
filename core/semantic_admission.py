"""Development-only evidence for source-admitted canonical statements.

The hashed source witness accompanies an editorial attestation of a direct
relation, never a theorem, inference premise, synonym assertion or prerequisite.
"""
import json

from django.conf import settings
from django.db import connection,ProgrammingError,OperationalError
from django.http import Http404,JsonResponse
from django.views.decorators.http import require_GET
from core.predicate_logical_projection import project_concept_admissions

def guard():
    if settings.IS_PRODUCTION or not getattr(settings,"V2_READ_PREVIEW_ENABLED",False):
        raise Http404("Admission preview disabled")

def unavailable():
    return JsonResponse({"error":"semantic admission database unavailable"},status=503,
                        headers={"Cache-Control":"no-store"})

@require_GET
def concept_admissions(request,concept_id):
    guard()
    try:
        limit=int(request.GET.get("limit","50"))
        offset=int(request.GET.get("offset","0"))
    except (TypeError,ValueError):
        return JsonResponse({"error":"invalid pagination"},status=400)
    if not 1<=limit<=100 or not 0<=offset<=10000:
        return JsonResponse({"error":"invalid pagination"},status=400)
    try:
        with connection.cursor() as cur:
            cur.execute("select id,slug,label from knowledge.concept where id=%s",[concept_id])
            concept=cur.fetchone()
            if concept is None:
                raise Http404("Unknown concept")
            cur.execute("""
              select s.id,s.subject_concept_id,s.predicate_slug,s.object_concept_id,
                     a.review_record,p.policy_record
                from knowledge.statement s
                join knowledge.statement_admission a on a.statement_id=s.id
                join knowledge.predicate_semantic_policy p on p.predicate_slug=s.predicate_slug
               where s.subject_concept_id=%s or s.object_concept_id=%s
               order by s.id limit %s offset %s
            """,[concept_id,concept_id,limit+1,offset])
            rows=cur.fetchall()
    except (ProgrammingError,OperationalError):
        return unavailable()
    statements=[]
    for sid,subject,predicate,obj,attestation,policy in rows[:limit]:
        # Django's PostgreSQL backend may return JSONB as an encoded JSON string.
        attestation = json.loads(attestation) if isinstance(attestation, str) else attestation
        policy = json.loads(policy) if isinstance(policy, str) else policy
        # Trust flags are enforced in the PostgreSQL source-admission schema.
        statements.append({
            "statement_id":str(sid),
            "subject_concept_id":str(subject),
            "subject_label":attestation.get("subject_label"),
            "object_label":attestation.get("object_label"),
            "predicate":predicate,
            "object_concept_id":str(obj),
            "direction":"outgoing" if subject==concept_id else "incoming",
            "predicate_policy":{
                "semantics":policy["semantics"],
                "logical_translation":policy.get("logical_translation"),
                "semantic_scope":policy["semantic_scope"],
                "transitive":False,"subtype_inference_eligible":False,
                "prerequisite_inference_eligible":False,
                "formal_proof_eligible":False,
            },
            "evidence":{
                "source_id":attestation["source_id"],
                "original_predicate":attestation["native_predicate"],
                "original_source_assertion":attestation["source_assertion_witness"],
                "source_archive_sha256":attestation.get("source_archive_sha256"),
                "references":attestation["evidence_urls"],
                "review_level":attestation["review_level"],
                "review_method":attestation.get("review_method"),
                "scope_note":attestation.get("scope_note"),
                "independent_expert_review":False,
                "source_subject_uri":attestation["subject_source_uri"],
                "source_object_uri":attestation["object_source_uri"],
            },
            "review_state":"editorially_screened_not_expert_verified",
            "inference_eligible":False,
            "proof_eligible":False,
        })
    return JsonResponse({
        "logical_projection":project_concept_admissions(str(concept_id),statements),
        "contract_version":"semantic-admission-preview@1",
        "public_release_verified":False,
        "concept":{"id":str(concept[0]),"slug":concept[1],"label":concept[2]},
        "review_level":"source_attestation_with_editorial_screen",
        "independent_expert_review":False,
        "limit":limit,"offset":offset,"has_more":len(rows)>limit,
        "results":statements,
    },headers={"Cache-Control":"no-store"})

@require_GET
def predicate_policies(request):
    guard()
    try:
        with connection.cursor() as cur:
            cur.execute("select policy_record from knowledge.predicate_semantic_policy order by predicate_slug limit 100")
            policies=[
                json.loads(row[0]) if isinstance(row[0], str) else row[0]
                for row in cur.fetchall()
            ]
    except (ProgrammingError,OperationalError):
        return unavailable()
    return JsonResponse({
        "contract_version":"semantic-predicate-preview@1",
        "public_release_verified":False,
        "proof_eligible":False,
        "policies":policies,
    },headers={"Cache-Control":"no-store"})
