"""Read-only v2 concept identity adapter for the forthcoming PostgreSQL cutover.

This module does not change the legacy Django ORM or public /v1 routes.
Data-owned schemas remain the authority; this adapter keeps UUID identity
distinct from mutable, human-readable public slugs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping
from uuid import UUID

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True, slots=True)
class CanonicalConcept:
    id: UUID
    slug: str
    label: str

    @classmethod
    def from_record(cls, row: Mapping[str, object]) -> "CanonicalConcept":
        if set(row) != {"id", "slug", "label"}:
            raise ValueError("v2 concept records require only id, slug and label")
        if not isinstance(row["id"], str):
            raise ValueError("v2 concept id must be a UUID string")
        try:
            identifier = UUID(row["id"])
        except (ValueError, AttributeError) as exc:
            raise ValueError("invalid v2 concept UUID") from exc
        if not isinstance(row["slug"], str) or not SLUG_PATTERN.fullmatch(row["slug"]):
            raise ValueError("invalid v2 concept slug")
        if not isinstance(row["label"], str) or not row["label"].strip():
            raise ValueError("v2 concept label cannot be blank")
        return cls(id=identifier, slug=row["slug"], label=row["label"].strip())

    def as_public_summary(self) -> dict[str, str]:
        """Preserve existing public slug-only response compatibility."""
        return {"slug": self.slug}


class ConceptIndex:
    """Snapshot-local lookup; not a replacement for runtime database indexing."""

    def __init__(self, rows: Iterable[Mapping[str, object]]) -> None:
        self.by_id: dict[UUID, CanonicalConcept] = {}
        self.by_slug: dict[str, CanonicalConcept] = {}
        for row in rows:
            concept = CanonicalConcept.from_record(row)
            if concept.id in self.by_id:
                raise ValueError(f"duplicate concept UUID: {concept.id}")
            if concept.slug in self.by_slug:
                raise ValueError(f"duplicate concept slug: {concept.slug}")
            self.by_id[concept.id] = concept
            self.by_slug[concept.slug] = concept

    def resolve_slug(self, slug: str) -> CanonicalConcept | None:
        return self.by_slug.get(slug)

    def resolve_id(self, identifier: UUID) -> CanonicalConcept | None:
        return self.by_id.get(identifier)
