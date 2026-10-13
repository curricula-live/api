"""Public, read-only, bounded Atlas development preview.

This intentionally follows the existing *unauthenticated* v2 preview gate.
It is not the published API and never exposes owner/admin tables, identities,
unreviewed private submissions or misleading publication/review claims.
"""
from __future__ import annotations

from django.conf import settings
from django.db import connection, OperationalError, ProgrammingError
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET

# Deliberately small vertical slice, IDs come from the canonical database.
OS_SLUGS = (
    "operating-system", "process", "thread", "file-system",
    "memory", "cpu", "processor",
)
OTHER_SLUGS = ("algorithm", "computer-network", "database")
PREVIEW_SLUGS = OS_SLUGS + OTHER_SLUGS


@require_GET
def atlas_preview(request):
    if settings.IS_PRODUCTION or not getattr(settings, "V2_READ_PREVIEW_ENABLED", False):
        raise Http404("Unavailable")

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """select id, slug, label from knowledge.concept
                   where slug = any(%s) order by label limit 20""",
                [list(PREVIEW_SLUGS)],
            )
            rows = cursor.fetchall()
            identifiers = [row[0] for row in rows]
            statements = []
            if identifiers:
                cursor.execute(
                    """select id, subject_concept_id, object_concept_id, predicate_slug
                       from knowledge.statement
                       where subject_concept_id = any(%s::uuid[])
                         and object_concept_id = any(%s::uuid[])
                       order by id limit 100""",
                    [identifiers, identifiers],
                )
                statements = cursor.fetchall()
    except (ProgrammingError, OperationalError):
        return JsonResponse(
            {"error": "v2 preview database unavailable"},
            status=503,
            headers={"Cache-Control": "no-store"},
        )

    return JsonResponse({
        "contract_version": "atlas-preview@1",
        "release_verified": False,
        "review_verified": False,
        "data_source": "staging-knowledge-v2",
        "concepts": [
            {"id": str(identifier), "slug": slug, "label": label,
             "area_hint": "Operating Systems" if slug in OS_SLUGS else
             {"algorithm": "Algorithms", "computer-network": "Computer Networks",
              "database": "Databases"}[slug],
             "review_state": "unverified"}
            for identifier, slug, label in rows
        ],
        "relationships": [
            {"id": str(identifier), "from": str(subject),
             "to": str(object_id), "type": predicate,
             "review_state": "unverified"}
            for identifier, subject, object_id, predicate in statements
        ],
        "definitions": [],
        "references": [],
    }, headers={"Cache-Control": "no-store"})
