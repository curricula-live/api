import json

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from core.models import SemanticPublicationSnapshot
from core.semantic import validate_plan


def _problem(code, detail, status):
    return JsonResponse(
        {"detail": {"code": code, "detail": detail}},
        status=status,
    )


@require_POST
def semantic_plan_validate(request):
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return _problem("INVALID_JSON", "Request body must be valid JSON.", 400)

    if not isinstance(payload, dict):
        return _problem("INVALID_REQUEST", "Request body must be a JSON object.", 400)

    snapshot_id = payload.get("snapshot_id")
    if not isinstance(snapshot_id, str) or not snapshot_id:
        return _problem("SNAPSHOT_REQUIRED", "snapshot_id is required.", 400)

    snapshot = SemanticPublicationSnapshot.objects.filter(snapshot_id=snapshot_id).first()
    if snapshot is None:
        return _problem(
            "UNSUPPORTED_SNAPSHOT",
            f"Snapshot {snapshot_id} is not published by this service.",
            404,
        )

    expected_schema = payload.get("expected_schema_version", snapshot.schema_version)
    if expected_schema != snapshot.schema_version:
        return _problem(
            "SCHEMA_VERSION_MISMATCH",
            (
                f"Snapshot {snapshot_id} uses schema {snapshot.schema_version}; "
                f"request expected {expected_schema}."
            ),
            409,
        )

    requested_policy = payload.get("policy_version", snapshot.policy_version)
    if requested_policy != snapshot.policy_version:
        return _problem(
            "POLICY_VERSION_MISMATCH",
            (
                f"Snapshot {snapshot_id} uses policy {snapshot.policy_version}; "
                f"request selected {requested_policy}."
            ),
            409,
        )

    context = payload.get("context", {})
    prior = payload.get("prior", [])
    plan = payload.get("plan")

    if not isinstance(context, dict):
        return _problem("INVALID_CONTEXT", "context must be an object.", 400)
    if not isinstance(prior, list):
        return _problem("INVALID_PRIOR", "prior must be an array.", 400)
    if not isinstance(plan, list) or not plan:
        return _problem("INVALID_PLAN", "plan must be a non-empty array.", 400)
    if not all(isinstance(item, dict) for item in prior + plan):
        return _problem(
            "INVALID_PLAN_ITEM",
            "prior and plan items must be objects containing ref and kind.",
            400,
        )

    validation = validate_plan(snapshot, context, prior, plan)
    validation["snapshot"] = snapshot.snapshot_id
    validation["policy"] = snapshot.policy_version

    return JsonResponse(
        {
            "contract_version": "semantic-api@1",
            "schema_version": snapshot.schema_version,
            "snapshot_hash": snapshot.content_hash,
            "validation": validation,
        }
    )
