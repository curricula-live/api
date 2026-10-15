"""Published UUID knowledge reads. Public access is gated by a verified release marker."""
from __future__ import annotations

import re

from django.conf import settings
from django.db import connection, OperationalError, ProgrammingError
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET

RELEASE = re.compile(r"^[0-9a-f]{40}$")


def _page(request):
    try:
        limit = int(request.GET.get("limit", "50"))
        offset = int(request.GET.get("offset", "0"))
    except ValueError:
        return None
    return (limit, offset) if 1 <= limit <= 100 and 0 <= offset <= 10000 else None


def _released(cursor):
    expected = getattr(settings, "PUBLIC_V2_RELEASE_COMMIT", "")
    if not getattr(settings, "PUBLIC_V2_ENABLED", False) or not RELEASE.fullmatch(expected):
        raise Http404("Knowledge release unavailable")
    cursor.execute("select git_commit from knowledge.publication where singleton = true")
    row = cursor.fetchone()
    if row is None or row[0] != expected:
        raise RuntimeError("Knowledge release mismatch")
    return expected


def _run(reader):
    expected = getattr(settings, "PUBLIC_V2_RELEASE_COMMIT", "")
    if not getattr(settings, "PUBLIC_V2_ENABLED", False) or not RELEASE.fullmatch(expected):
        raise Http404("Knowledge release unavailable")
    try:
        with connection.cursor() as cursor:
            release = _released(cursor)
            payload = reader(cursor)
    except (ProgrammingError, OperationalError, RuntimeError):
        return JsonResponse({"error": "published knowledge unavailable"}, status=503,
                            headers={"Cache-Control": "no-store"})
    return JsonResponse({"contract_version": "knowledge-v2@1", "release_commit": release,
                         **payload}, headers={"Cache-Control": "no-store"})


def _concept(row):
    return {"id": str(row[0]), "slug": row[1], "label": row[2]}


@require_GET
def concepts(request):
    page = _page(request)
    q = request.GET.get("q", "").strip()
    if page is None or len(q) > 80 or len(q) == 1:
        return JsonResponse({"error": "invalid query or pagination"}, status=400)
    limit, offset = page

    def read(cursor):
        pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        cursor.execute("""select id, slug, label from knowledge.concept
                          where (%s = '' or label ilike %s or slug ilike %s)
                          order by label, id limit %s offset %s""",
                       [q, pattern, pattern, limit + 1, offset])
        rows = cursor.fetchall()
        return {"results": [_concept(row) for row in rows[:limit]],
                "limit": limit, "offset": offset, "has_more": len(rows) > limit}

    return _run(read)


@require_GET
def concept_detail(request, concept_id):
    def read(cursor):
        cursor.execute("select id, slug, label from knowledge.concept where id = %s", [concept_id])
        row = cursor.fetchone()
        if row is None:
            raise Http404("Unknown concept")
        cursor.execute("""select s.id, s.predicate_slug, s.subject_concept_id,
                          s.subject_statement_id, s.object_concept_id,
                          s.object_statement_id, s.literal_value, s.literal_datatype
                          from knowledge.definition_statement ds
                          join knowledge.statement s on s.id = ds.statement_id
                          where ds.concept_id = %s order by ds.position limit 101""", [concept_id])
        definition_rows = cursor.fetchall()
        if len(definition_rows) > 100:
            raise RuntimeError("Definition exceeds contract bound")
        return {"concept": _concept(row),
                "definition": {"status": "present", "statements": [_statement(r) for r in definition_rows]}
                if definition_rows else {"status": "missing", "statements": []},
                "evidence": {"status": "missing", "references": []},
                "classification": {"status": "unavailable", "memberships": []}}

    return _run(read)


def _statement(row):
    sid, predicate, subject_concept, subject_statement, object_concept, object_statement, literal, datatype = row
    subject = {"kind": "concept", "id": str(subject_concept)} if subject_concept else {"kind": "statement", "id": str(subject_statement)}
    if object_concept:
        target = {"kind": "concept", "id": str(object_concept)}
    elif object_statement:
        target = {"kind": "statement", "id": str(object_statement)}
    else:
        target = {"kind": "literal", "datatype": datatype, "value": literal}
    return {"id": str(sid), "predicate": predicate, "subject": subject,
            "object": target, "review_state": "unreviewed", "evidence": {"status": "missing", "references": []}}


@require_GET
def concept_statements(request, concept_id):
    page = _page(request)
    if page is None:
        return JsonResponse({"error": "invalid pagination"}, status=400)
    limit, offset = page

    def read(cursor):
        cursor.execute("select 1 from knowledge.concept where id = %s", [concept_id])
        if cursor.fetchone() is None:
            raise Http404("Unknown concept")
        cursor.execute("""select id, predicate_slug, subject_concept_id,
                          subject_statement_id, object_concept_id,
                          object_statement_id, literal_value, literal_datatype
                          from knowledge.statement
                          where subject_concept_id = %s or object_concept_id = %s
                          order by id limit %s offset %s""",
                       [concept_id, concept_id, limit + 1, offset])
        rows = cursor.fetchall()
        return {"concept_id": str(concept_id), "results": [_statement(row) for row in rows[:limit]],
                "limit": limit, "offset": offset, "has_more": len(rows) > limit}

    return _run(read)
