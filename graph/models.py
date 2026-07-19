import uuid
import re

from django.core.exceptions import ValidationError
from django.db import models


def validate_relation_type(value):
    if not re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", value):
        raise ValidationError("Relation types must be lowercase snake_case.")


class Concept(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=160, unique=True)
    label = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "concept"
        ordering = ["slug"]

    def __str__(self):
        return self.label


class Relation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(
        Concept,
        on_delete=models.CASCADE,
        related_name="outgoing_relations",
        db_column="source",
    )
    target = models.ForeignKey(
        Concept,
        on_delete=models.CASCADE,
        related_name="incoming_relations",
        db_column="target",
    )
    type = models.SlugField(
        max_length=64,
        validators=[validate_relation_type],
        help_text="Extensible relation predicate, for example prerequisite_of or part_of.",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "relation"
        constraints = [
            models.UniqueConstraint(
                fields=["source", "target", "type"],
                name="unique_typed_relation",
            )
        ]
        indexes = [
            models.Index(fields=["source", "type"], name="relation_source_type_idx"),
            models.Index(fields=["target", "type"], name="relation_target_type_idx"),
        ]

    def clean(self):
        super().clean()
        if self.source_id == self.target_id and self.type not in {"equivalent_to", "related_to"}:
            raise ValidationError("Self-relations are only allowed for equivalent_to or related_to.")

    def __str__(self):
        return f"{self.source.slug} —{self.type}→ {self.target.slug}"
