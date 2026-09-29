import json
import uuid

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse

from core.models import Concept, Relation, RelationType
from core.semantic import SnapshotConflict, SnapshotCycle, publish_snapshot


pytestmark = pytest.mark.django_db


def add_prerequisite(source, target, *, relation_id, scope=None, evidence=None):
    relation_type, _ = RelationType.objects.get_or_create(slug="prerequisite_of")
    return Relation.objects.create(
        id=relation_id,
        source=Concept.objects.get(slug=source),
        type=relation_type,
        target=Concept.objects.get(slug=target),
        metadata={
            "scope": scope or {},
            "evidence": evidence or [],
        },
    )


@pytest.fixture
def publication_graph(db):
    for slug in ("C1", "C2", "C3", "unrelated"):
        Concept.objects.create(slug=slug)

    edge_1 = add_prerequisite(
        "C1",
        "C2",
        relation_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        evidence=["EV-1"],
    )
    edge_2 = add_prerequisite(
        "C2",
        "C3",
        relation_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        evidence=["EV-2"],
    )
    return edge_1, edge_2


def validate(client, snapshot, *, prior, plan, context=None, **overrides):
    body = {
        "snapshot_id": snapshot,
        "policy_version": "strict-prior@1",
        "expected_schema_version": "sem-v1",
        "context": context
        or {
            "context_id": "test",
            "subject": "computer_science",
            "course_context": "number_representation",
        },
        "prior": [{"ref": ref, "kind": "concept"} for ref in prior],
        "plan": [{"ref": ref, "kind": "concept"} for ref in plan],
        **overrides,
    }
    return client.post(
        reverse("semantic-plan-validate"),
        data=json.dumps(body),
        content_type="application/json",
    )


def test_publish_snapshot_is_deterministic_and_idempotent(publication_graph):
    first, created = publish_snapshot("K_17")
    second, recreated = publish_snapshot("K_17")

    assert created is True
    assert recreated is False
    assert first.content_hash == second.content_hash
    assert len(first.content_hash) == 64
    assert first.manifest["concepts"] == ["C1", "C2", "C3", "unrelated"]
    assert len(first.manifest["edges"]) == 2


def test_snapshot_identifier_cannot_be_reused_for_changed_content(publication_graph):
    publish_snapshot("K_17")
    publication_graph[1].delete()

    with pytest.raises(SnapshotConflict):
        publish_snapshot("K_17")


def test_publisher_rejects_prerequisite_cycles(db):
    for slug in ("C1", "C2"):
        Concept.objects.create(slug=slug)
    add_prerequisite(
        "C1",
        "C2",
        relation_id=uuid.UUID("00000000-0000-0000-0000-000000000011"),
    )
    add_prerequisite(
        "C2",
        "C1",
        relation_id=uuid.UUID("00000000-0000-0000-0000-000000000012"),
    )

    with pytest.raises(SnapshotCycle, match="cycle"):
        publish_snapshot("K_cycle")


def test_management_command_publishes_snapshot(publication_graph, capsys):
    call_command("publish_semantic_snapshot", "K_cmd")
    output = capsys.readouterr().out
    assert "Published K_cmd" in output


def test_management_command_rejects_conflicting_republication(publication_graph):
    call_command("publish_semantic_snapshot", "K_cmd")
    publication_graph[1].delete()

    with pytest.raises(CommandError, match="different immutable content"):
        call_command("publish_semantic_snapshot", "K_cmd")


def test_plan_validation_detects_late_intra_plan_prerequisite(client, publication_graph):
    snapshot, _ = publish_snapshot("K_17")
    response = validate(client, snapshot.snapshot_id, prior=["C1"], plan=["C3", "C2"])

    assert response.status_code == 200
    payload = response.json()
    assert payload["contract_version"] == "semantic-api@1"
    assert payload["snapshot_hash"] == snapshot.content_hash
    assert payload["validation"]["outcome"] == "INVALID"

    certificate = payload["validation"]["certificates"][0]
    assert certificate["target_concept"] == "C3"
    assert certificate["missing_or_late_concept"] == "C2"
    assert certificate["violation_kind"] == "intra_plan_order"
    assert certificate["source_evidence"] == ["EV-2"]


def test_plan_validation_accepts_correct_order(client, publication_graph):
    publish_snapshot("K_17")
    response = validate(client, "K_17", prior=["C1"], plan=["C2", "C3"])

    assert response.status_code == 200
    assert response.json()["validation"]["outcome"] == "VALID"


def test_historical_snapshot_replay_survives_live_graph_change(client, publication_graph):
    k17, _ = publish_snapshot("K_17")

    publication_graph[1].delete()
    k18, _ = publish_snapshot("K_18")

    old = validate(client, "K_17", prior=["C1"], plan=["C3", "C2"]).json()
    current = validate(client, "K_18", prior=["C1"], plan=["C3", "C2"]).json()

    assert old["validation"]["outcome"] == "INVALID"
    assert current["validation"]["outcome"] == "VALID"
    assert old["snapshot_hash"] == k17.content_hash
    assert current["snapshot_hash"] == k18.content_hash
    assert k17.content_hash != k18.content_hash


def test_unknown_concept_is_indeterminate(client, publication_graph):
    publish_snapshot("K_17")
    response = validate(client, "K_17", prior=["C1"], plan=["missing"])

    assert response.status_code == 200
    result = response.json()["validation"]
    assert result["outcome"] == "INDETERMINATE"
    assert result["unresolved_refs"] == ["missing"]


def test_relevant_unknown_scope_is_indeterminate(client, db):
    for slug in ("C1", "C2"):
        Concept.objects.create(slug=slug)
    edge = add_prerequisite(
        "C1",
        "C2",
        relation_id=uuid.UUID("00000000-0000-0000-0000-000000000021"),
        scope={"stage": "upper_secondary", "subject": "computer_science"},
    )
    publish_snapshot("K_scope")

    response = validate(
        client,
        "K_scope",
        prior=[],
        plan=["C2"],
        context={
            "context_id": "scope-test",
            "stage": "*",
            "subject": "computer_science",
            "course_context": "number_representation",
        },
    )

    assert response.status_code == 200
    result = response.json()["validation"]
    assert result["outcome"] == "INDETERMINATE"
    assert result["unknown_scope_assertions"] == [str(edge.id)]


@pytest.mark.parametrize(
    ("overrides", "status", "code"),
    [
        ({"snapshot_id": "missing"}, 404, "UNSUPPORTED_SNAPSHOT"),
        ({"expected_schema_version": "sem-v2"}, 409, "SCHEMA_VERSION_MISMATCH"),
        ({"policy_version": "other-policy"}, 409, "POLICY_VERSION_MISMATCH"),
    ],
)
def test_contract_rejects_unknown_snapshot_schema_or_policy(
    client, publication_graph, overrides, status, code
):
    publish_snapshot("K_17")
    body = {
        "snapshot_id": "K_17",
        "policy_version": "strict-prior@1",
        "expected_schema_version": "sem-v1",
        "context": {"subject": "computer_science", "course_context": "number_representation"},
        "prior": [],
        "plan": [{"ref": "C2", "kind": "concept"}],
        **overrides,
    }
    response = client.post(
        reverse("semantic-plan-validate"),
        data=json.dumps(body),
        content_type="application/json",
    )

    assert response.status_code == status
    assert response.json()["detail"]["code"] == code


def test_plan_validation_rejects_empty_plan(client, publication_graph):
    publish_snapshot("K_17")
    response = client.post(
        reverse("semantic-plan-validate"),
        data=json.dumps({"snapshot_id": "K_17", "context": {}, "prior": [], "plan": []}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_PLAN"


def test_plan_validation_is_post_only(client, publication_graph):
    publish_snapshot("K_17")
    response = client.get(reverse("semantic-plan-validate"))
    assert response.status_code == 405
