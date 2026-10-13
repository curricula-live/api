"""Unmanaged v2 read-model matching data-owned knowledge.concept DDL.

This model is deliberately NOT a migration source. The `data` repository owns
the knowledge schema. No public view consumes it before the coordinated cutover.
"""
from django.db import models


class V2Concept(models.Model):
    id = models.UUIDField(primary_key=True)
    slug = models.TextField(unique=True)
    label = models.TextField()

    class Meta:
        managed = False
        db_table = '"knowledge"."concept"'
        app_label = "core"

    def __str__(self) -> str:
        return self.slug


class V2Predicate(models.Model):
    """Read-only mapping to data-owned knowledge.predicate (slug identity)."""

    slug = models.TextField(primary_key=True)
    label = models.TextField()

    class Meta:
        managed = False
        db_table = '"knowledge"."predicate"'
        app_label = "core"


class V2Statement(models.Model):
    """Typed UUID-backed statement mapping; data owns all FK/check constraints.

    Both subject and object can reference statements as well as concepts.
    The model intentionally does not infer a single concept-to-concept edge.
    """

    id = models.UUIDField(primary_key=True)
    subject_concept = models.ForeignKey(
        V2Concept, db_column="subject_concept_id", null=True,
        on_delete=models.DO_NOTHING, related_name="+",
    )
    subject_statement = models.ForeignKey(
        "self", db_column="subject_statement_id", null=True,
        on_delete=models.DO_NOTHING, related_name="+",
    )
    predicate = models.ForeignKey(
        V2Predicate, db_column="predicate_slug", to_field="slug",
        on_delete=models.DO_NOTHING, related_name="+",
    )
    object_concept = models.ForeignKey(
        V2Concept, db_column="object_concept_id", null=True,
        on_delete=models.DO_NOTHING, related_name="+",
    )
    object_statement = models.ForeignKey(
        "self", db_column="object_statement_id", null=True,
        on_delete=models.DO_NOTHING, related_name="+",
    )
    literal_value = models.JSONField(null=True)
    literal_datatype = models.TextField(null=True)

    class Meta:
        managed = False
        db_table = '"knowledge"."statement"'
        app_label = "core"
