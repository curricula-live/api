import uuid

from django.core.exceptions import ValidationError
from django.db import models

RELATION_TYPES = [
    "prerequisite_of", "part_of", "type_of", "instance_of", "uses", "used_by",
    "depends_on", "equivalent_to", "overlaps_with", "assessed_by", "introduces",
    "input_for", "output_of", "stored_in", "processed_by", "communicates_with",
    "controls", "represented_by", "related_to",
]


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
    type = models.CharField(max_length=64, choices=[(value, value) for value in RELATION_TYPES])
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
        if self.source_id == self.target_id and self.type not in {"equivalent_to", "related_to"}:
            raise ValidationError("Self-relations are only allowed for equivalent_to or related_to.")

    def __str__(self):
        return f"{self.source.slug} —{self.type}→ {self.target.slug}"
