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
