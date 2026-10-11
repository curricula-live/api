"""V2 UUID/slugs boundary tests; no database or fixture connection required."""
from uuid import UUID

import pytest

from core.knowledge_v2 import CanonicalConcept, ConceptIndex

ID = "c74fe051-ac5e-521b-8770-3180fb0decb6"


def test_resolve_by_public_slug_and_uuid() -> None:
    index = ConceptIndex([{"id": ID, "slug": "operating-system", "label": "Operating System"}])
    concept = index.resolve_slug("operating-system")
    assert concept is not None
    assert concept.id == UUID(ID)
    assert index.resolve_id(UUID(ID)) == concept
    assert concept.as_public_summary() == {"slug": "operating-system"}


def test_slug_rename_keeps_canonical_identity() -> None:
    old = CanonicalConcept.from_record({"id": ID, "slug": "operating-system", "label": "OS"})
    renamed = CanonicalConcept.from_record({"id": ID, "slug": "operating-systems", "label": "OS"})
    assert old.id == renamed.id
    assert old.slug != renamed.slug


def test_reject_duplicate_uuids() -> None:
    with pytest.raises(ValueError, match="duplicate concept UUID"):
        ConceptIndex([
            {"id": ID, "slug": "first", "label": "First"},
            {"id": ID, "slug": "second", "label": "Second"},
        ])


def test_reject_invalid_slug_and_opaque_description() -> None:
    with pytest.raises(ValueError, match="slug"):
        CanonicalConcept.from_record({"id": ID, "slug": "Wrong_Slug", "label": "OS"})
    with pytest.raises(ValueError, match="only id"):
        CanonicalConcept.from_record({
            "id": ID, "slug": "operating-system", "label": "OS", "description": "Legacy text"
        })


def test_blank_label_is_invalid() -> None:
    with pytest.raises(ValueError, match="label"):
        CanonicalConcept.from_record({"id": ID, "slug": "operating-system", "label": " "})
