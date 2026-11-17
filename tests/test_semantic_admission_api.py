from unittest.mock import patch
from uuid import UUID
from django.db import ProgrammingError
from django.test import override_settings
from django.urls import reverse

CID=UUID("11111111-1111-4111-8111-111111111111")
OTHER=UUID("22222222-2222-4222-8222-222222222222")
SID=UUID("33333333-3333-4333-8333-333333333333")
CONCEPT_ROUTE=reverse("v2-preview-concept-admissions",kwargs={"concept_id":CID})
POLICY_ROUTE=reverse("v2-preview-predicate-semantic-policies")
RECORD={"source_id":"cso@3.5","native_predicate":"http://cso.kmi.open.ac.uk/schema/cso#superTopicOf",
 "source_assertion_witness":"sha256:abc","evidence_urls":["https://cso.kmi.open.ac.uk/about"],
 "review_level":"editorially_screened_source_attested",
 "subject_source_uri":"https://cso.kmi.open.ac.uk/topics/artificial_intelligence",
 "object_source_uri":"https://cso.kmi.open.ac.uk/topics/machine_learning"}
POLICY={"slug":"research_topic_parent_of","semantics":"CSO research-area parent relation",
        "semantic_scope":"research_topic_direct_organizational_hierarchy",
        "transitive":False,"safe_for_subtype_inference":False,
        "safe_for_prerequisite_inference":False,
        "safe_for_formal_proof":False}

def test_all_off_by_default(client):
    with patch("core.semantic_admission.connection.cursor") as db:
        assert client.get(CONCEPT_ROUTE).status_code==404
        assert client.get(POLICY_ROUTE).status_code==404
        db.assert_not_called()

@override_settings(IS_PRODUCTION=True,V2_READ_PREVIEW_ENABLED=True)
def test_never_in_production(client):
    with patch("core.semantic_admission.connection.cursor") as db:
        assert client.get(CONCEPT_ROUTE).status_code==404
        assert client.get(POLICY_ROUTE).status_code==404
        db.assert_not_called()

@override_settings(IS_PRODUCTION=False,V2_READ_PREVIEW_ENABLED=True)
def test_concept_admissions_have_witness_and_semantic_policy(client):
    with patch("core.semantic_admission.connection.cursor") as db:
        cur=db.return_value.__enter__.return_value
        cur.fetchone.return_value=(CID,"artificial-intelligence","Artificial intelligence")
        cur.fetchall.return_value=[(SID,CID,"research_topic_parent_of",OTHER,RECORD,POLICY)]
        response=client.get(CONCEPT_ROUTE+"?limit=1")
    assert response.status_code==200
    assert response["Cache-Control"]=="no-store"
    x=response.json()
    assert x["independent_expert_review"] is False
    assert x["public_release_verified"] is False
    assert x["has_more"] is False
    s=x["results"][0]
    assert s["statement_id"]==str(SID)
    assert s["direction"]=="outgoing"
    assert s["evidence"]["original_predicate"].endswith("superTopicOf")
    assert s["evidence"]["references"]==["https://cso.kmi.open.ac.uk/about"]
    assert s["predicate_policy"]["subtype_inference_eligible"] is False
    assert s["predicate_policy"]["prerequisite_inference_eligible"] is False
    assert s["predicate_policy"]["formal_proof_eligible"] is False
    assert s["inference_eligible"] is False
    assert cur.execute.call_count==2
    assert cur.execute.call_args.args[1]==[CID,CID,2,0]

@override_settings(IS_PRODUCTION=False,V2_READ_PREVIEW_ENABLED=True)
def test_predicate_policy_route(client):
    with patch("core.semantic_admission.connection.cursor") as db:
        cur=db.return_value.__enter__.return_value
        cur.fetchall.return_value=[(POLICY,)]
        response=client.get(POLICY_ROUTE)
    assert response.status_code==200
    assert response.json()["policies"][0]["slug"]=="research_topic_parent_of"
    assert response.json()["proof_eligible"] is False

@override_settings(IS_PRODUCTION=False,V2_READ_PREVIEW_ENABLED=True)
def test_invalid_limits_and_get_only_without_queries(client):
    with patch("core.semantic_admission.connection.cursor") as db:
        for suffix in ("?limit=0","?limit=101","?limit=garbage","?offset=-1","?offset=10001"):
            assert client.get(CONCEPT_ROUTE+suffix).status_code==400
        assert client.post(CONCEPT_ROUTE).status_code==405
        assert client.post(POLICY_ROUTE).status_code==405
        db.assert_not_called()

@override_settings(IS_PRODUCTION=False,V2_READ_PREVIEW_ENABLED=True)
def test_missing_schema_fails_closed(client):
    with patch("core.semantic_admission.connection.cursor",side_effect=ProgrammingError("sensitive")):
        response=client.get(CONCEPT_ROUTE)
    assert response.status_code==503
    assert "sensitive" not in response.content.decode()

@override_settings(IS_PRODUCTION=False,V2_READ_PREVIEW_ENABLED=True)
def test_unknown_concept_never_fabricated(client):
    with patch("core.semantic_admission.connection.cursor") as db:
        cur=db.return_value.__enter__.return_value
        cur.fetchone.return_value=None
        response=client.get(CONCEPT_ROUTE)
    assert response.status_code==404
    assert cur.execute.call_count==1

@override_settings(IS_PRODUCTION=False,V2_READ_PREVIEW_ENABLED=True)
def test_django_postgres_jsonb_string_decoder(client):
    import json
    with patch("core.semantic_admission.connection.cursor") as db:
        cur=db.return_value.__enter__.return_value
        cur.fetchone.return_value=(CID,"artificial-intelligence","Artificial intelligence")
        cur.fetchall.return_value=[(SID,CID,"research_topic_parent_of",OTHER,
                                     json.dumps(RECORD),json.dumps(POLICY))]
        response=client.get(CONCEPT_ROUTE)
    assert response.status_code==200
    assert response.json()["results"][0]["evidence"]["source_id"]=="cso@3.5"
    with patch("core.semantic_admission.connection.cursor") as db:
        db.return_value.__enter__.return_value.fetchall.return_value=[(json.dumps(POLICY),)]
        response=client.get(POLICY_ROUTE)
    assert response.status_code==200
    assert response.json()["policies"][0]["semantic_scope"]==POLICY["semantic_scope"]
