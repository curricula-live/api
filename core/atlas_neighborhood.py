"""Unauthenticated bounded canonical concept relationships for the staging Atlas.

Reads only concept-to-concept statements in the data-owned knowledge schema.
The gate is the existing v2 *publication-preview* flag, not owner login.
Statements with literal/statement objects need a separately reviewed contract.
"""
from __future__ import annotations

from django.conf import settings
from django.db import connection, OperationalError, ProgrammingError
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET

MAX_LIMIT = 100
DEFAULT_LIMIT = 30
MAX_OFFSET = 10000


def _int_query(request, name, default, minimum, maximum):
    value = request.GET.get(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if minimum <= parsed <= maximum else None


@require_GET
def concept_relationships_preview(request, concept_id):
    if settings.IS_PRODUCTION or not getattr(settings, "V2_READ_PREVIEW_ENABLED", False):
        raise Http404("Unavailable")

    limit = _int_query(request, "limit", DEFAULT_LIMIT, 1, MAX_LIMIT)
    offset = _int_query(request, "offset", 0, 0, MAX_OFFSET)
    if limit is None or offset is None:
        return JsonResponse(
            {"error": "invalid pagination; limit 1..100, offset 0..10000"},
            status=400, headers={"Cache-Control": "no-store"},
        )

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "select id, slug, label from knowledge.concept where id = %s",
                [concept_id],
            )
            concept = cursor.fetchone()
            if concept is None:
                raise Http404("Unknown concept")
            cursor.execute(
                """select s.id, s.predicate_slug, s.subject_concept_id,
                          src.slug, src.label, s.object_concept_id,
                          dst.slug, dst.label
                   from knowledge.statement s
                   join knowledge.concept src on src.id = s.subject_concept_id
                   join knowledge.concept dst on dst.id = s.object_concept_id
                   where s.subject_concept_id = %s or s.object_concept_id = %s
                   order by s.id limit %s offset %s""",
                [concept_id, concept_id, limit + 1, offset],
            )
            rows = cursor.fetchall()
    except (ProgrammingError, OperationalError):
        return JsonResponse(
            {"error": "v2 preview database unavailable"},
            status=503, headers={"Cache-Control": "no-store"},
        )

    return JsonResponse({
        "contract_version": "atlas-neighborhood-preview@1",
        "release_verified": False,
        "review_verified": False,
        "concept": {"id": str(concept[0]), "slug": concept[1], "label": concept[2]},
        "limit": limit,
        "offset": offset,
        "has_more": len(rows) > limit,
        "relationships": [
            {
                "id": str(statement_id),
                "predicate": predicate,
                "source": {"id": str(source_id), "slug": source_slug, "label": source_label},
                "target": {"id": str(target_id), "slug": target_slug, "label": target_label},
                "direction": "outgoing" if source_id == concept_id else "incoming",
                "review_state": "unverified",
                "references": [],
            }
            for statement_id, predicate, source_id, source_slug, source_label,
                target_id, target_slug, target_label in rows[:limit]
        ],
    }, headers={"Cache-Control": "no-store"})
