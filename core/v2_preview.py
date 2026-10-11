"""Explicitly gated staging reads from data-owned knowledge.concept.

This is NOT the released v2 API. It has no release-pinning contract, academic
review guarantee, or owner-only data. Always disabled in production and by
default everywhere. Existing /v1 endpoints remain unchanged.
"""
from __future__ import annotations

from django.conf import settings
from django.db import OperationalError, ProgrammingError
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET

from core import knowledge_v2_repository


def _enabled() -> bool:
    return not settings.IS_PRODUCTION and getattr(settings, "V2_READ_PREVIEW_ENABLED", False)


def _response(concept) -> JsonResponse:
    if concept is None:
        raise Http404("Unknown concept")

    response = JsonResponse({
        "contract_version": "knowledge-v2-preview@1",
        "release_verified": False,
        "concept": {
            "id": str(concept.id),
            "slug": concept.slug,
            "label": concept.label,
        },
    })
    response["Cache-Control"] = "no-store"
    return response


def _read(reader, identity) -> JsonResponse:
    if not _enabled():
        raise Http404("Not available")

    try:
        concept = reader(identity)
    except (OperationalError, ProgrammingError):
        # Missing staging migration should not leak table names or SQL.
        return JsonResponse(
            {"error": "v2 preview database unavailable"},
            status=503,
            headers={"Cache-Control": "no-store"},
        )
    return _response(concept)


@require_GET
def concept_by_slug_preview(request, slug: str) -> JsonResponse:
    return _read(knowledge_v2_repository.get_concept_by_slug, slug)


@require_GET
def concept_by_id_preview(request, concept_id) -> JsonResponse:
    return _read(knowledge_v2_repository.get_concept_by_id, concept_id)
