from unittest.mock import patch
from uuid import UUID
from django.db import ProgrammingError
from django.test import override_settings
from django.urls import reverse

SEARCH=reverse("v2-preview-source-search")
REL=reverse("v2-preview-source-relations")
PRED=reverse("v2-preview-source-predicates")
URI="https://cso.kmi.open.ac.uk/topics/tcp"
CID=UUID("11111111-1111-4111-8111-111111111111")

def test_all_source_routes_off_by_default(client):
    with patch("core.source_discovery.connection.cursor") as cursor:
        assert client.get(SEARCH+"?q=tcp").status_code==404
        assert client.get(REL+"?source_id=cso%403.5&source_uri="+URI).status_code==404
        assert client.get(PRED+"?source_id=cso%403.5").status_code==404
        cursor.assert_not_called()

@override_settings(IS_PRODUCTION=True,V2_READ_PREVIEW_ENABLED=True)
def test_production_never_exposes_source_data(client):
    with patch("core.source_discovery.connection.cursor") as cursor:
        assert client.get(SEARCH+"?q=tcp").status_code==404
        cursor.assert_not_called()

@override_settings(IS_PRODUCTION=False,V2_READ_PREVIEW_ENABLED=True)
def test_source_search_preserves_native_source_identity(client):
    with patch("core.source_discovery.connection.cursor") as cursor:
        sql=cursor.return_value.__enter__.return_value
        sql.fetchall.return_value=[
            ("cso@3.5",URI,"tcp",[CID],"lexical_candidate_unreviewed"),
        ]
        result=client.get(SEARCH+"?q=tcp&limit=1")
    assert result.status_code==200
    assert result["Cache-Control"]=="no-store"
    body=result.json()
    assert body["source_review_verified"] is False
    assert body["canonical_identity_approved"] is False
    assert body["inference_eligible"] is False
    assert body["results"][0]["source_uri"]==URI
    assert body["results"][0]["canonical_candidate_ids"]==[str(CID)]
    assert sql.execute.call_count==1
    assert sql.execute.call_args.args[1][-2:]==[2,0]

@override_settings(IS_PRODUCTION=False,V2_READ_PREVIEW_ENABLED=True)
def test_relation_read_returns_witness_without_inference(client):
    with patch("core.source_discovery.connection.cursor") as cursor:
        sql=cursor.return_value.__enter__.return_value
        sql.fetchone.return_value=("cso@3.5",URI,"tcp")
        sql.fetchall.return_value=[("sha256:abc",URI,"http://cso.kmi.open.ac.uk/schema/cso#superTopicOf",
                                     "https://cso.kmi.open.ac.uk/topics/networks",
                                     [CID],[],"one_lexical_candidate_requires_review")]
        result=client.get(REL,{"source_id":"cso@3.5","source_uri":URI,"limit":1})
    assert result.status_code==200
    r=result.json()["relations"][0]
    assert r["native_predicate"].endswith("superTopicOf")
    assert r["source_assertion_witness"]=="sha256:abc"
    assert r["direction"]=="outgoing"
    assert r["inference_eligible"] is False
    assert sql.execute.call_count==2
    assert sql.execute.call_args.args[1]==["cso@3.5",URI,URI,2,0]

@override_settings(IS_PRODUCTION=False,V2_READ_PREVIEW_ENABLED=True)
def test_predicate_registry_is_unreviewed(client):
    with patch("core.source_discovery.connection.cursor") as cursor:
        sql=cursor.return_value.__enter__.return_value
        sql.fetchall.return_value=[("broaderTopic","historical_topic_broader_than",
                                      "topic_hierarchy","unreviewed_source_mapping")]
        result=client.get(PRED,{"source_id":"curricula-historical-v1@1.0.0"})
    assert result.status_code==200
    assert result.json()["predicates"][0]["inference_eligible"] is False

@override_settings(IS_PRODUCTION=False,V2_READ_PREVIEW_ENABLED=True)
def test_validation_and_get_only_do_not_query(client):
    with patch("core.source_discovery.connection.cursor") as cursor:
        for path in (SEARCH+"?q=a",SEARCH+"?q=tcp&limit=1000",
                     REL+"?source_id=unknown&source_uri="+URI,
                     REL+"?source_id=cso%403.5&source_uri=not-a-uri",
                     PRED+"?source_id=unknown"):
            assert client.get(path).status_code==400
        for path in (SEARCH,REL,PRED):
            assert client.post(path).status_code==405
        cursor.assert_not_called()

@override_settings(IS_PRODUCTION=False,V2_READ_PREVIEW_ENABLED=True)
def test_sql_errors_are_redacted(client):
    with patch("core.source_discovery.connection.cursor",
               side_effect=ProgrammingError("internal secret from database")):
        result=client.get(SEARCH+"?q=tcp")
    assert result.status_code==503
    assert "internal secret" not in result.content.decode()

@override_settings(IS_PRODUCTION=False,V2_READ_PREVIEW_ENABLED=True)
def test_missing_source_uri_is_not_synthesized(client):
    with patch("core.source_discovery.connection.cursor") as cursor:
        sql=cursor.return_value.__enter__.return_value
        sql.fetchone.return_value=None
        response=client.get(REL,{"source_id":"cso@3.5","source_uri":URI})
    assert response.status_code==404
    assert sql.execute.call_count==1
