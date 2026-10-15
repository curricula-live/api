"""Explicit read-only access to data-owned v2 concept rows.

No implicit legacy fallback is permitted; a missing knowledge schema should
surface as an operational error until the v2 release is published.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from core.knowledge_v2 import CanonicalConcept, SLUG_PATTERN
from core.knowledge_v2_models import V2Concept


def _to_concept(row: dict[str, Any] | None) -> CanonicalConcept | None:
    if row is None:
        return None
    return CanonicalConcept.from_record({
        "id": str(row["id"]),
        "slug": row["slug"],
        "label": row["label"],
    })


def get_concept_by_slug(slug: str, *, manager: Any = None) -> CanonicalConcept | None:
    """Resolve a public slug to the stable UUID using the actual v2 model."""
    if not isinstance(slug, str) or not SLUG_PATTERN.fullmatch(slug):
        return None
    query = V2Concept.objects if manager is None else manager
    return _to_concept(query.filter(slug=slug).values("id", "slug", "label").first())


def get_concept_by_id(identifier: UUID, *, manager: Any = None) -> CanonicalConcept | None:
    """Resolve an immutable canonical UUID independently of its current slug."""
    if not isinstance(identifier, UUID):
        raise ValueError("expected canonical UUID")
    query = V2Concept.objects if manager is None else manager
    return _to_concept(query.filter(id=identifier).values("id", "slug", "label").first())


def list_concepts(*, limit: int = 100, offset: int = 0, manager: Any = None) -> list[CanonicalConcept]:
    """Read a bounded page of canonical identities, ordered deterministically."""
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    if not isinstance(offset, int) or isinstance(offset, bool) or not 0 <= offset <= 100000:
        raise ValueError("offset must be between 0 and 100000")
    query = V2Concept.objects if manager is None else manager
    rows = query.order_by("slug", "id").values("id", "slug", "label")[offset:offset + limit]
    return [_to_concept(row) for row in rows]
