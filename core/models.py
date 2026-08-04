from django.db import models


class Concept(models.Model):
    slug = models.TextField(primary_key=True)

    class Meta:
        managed = False
        db_table = "concept"

    def __str__(self) -> str:
        return self.slug


class RelationType(models.Model):
    slug = models.TextField(primary_key=True)

    class Meta:
        managed = False
        db_table = "relation_type"

    def __str__(self) -> str:
        return self.slug


class Relation(models.Model):
    id = models.UUIDField(primary_key=True)

    source = models.ForeignKey(
        Concept,
        on_delete=models.CASCADE,
        db_column="source",
        related_name="outgoing_relations",
    )

    type = models.ForeignKey(
        RelationType,
        on_delete=models.RESTRICT,
        db_column="type",
        related_name="relations",
    )

    target = models.ForeignKey(
        Concept,
        on_delete=models.CASCADE,
        db_column="target",
        related_name="incoming_relations",
    )

    class Meta:
        managed = False
        db_table = "relation"
        constraints = [
            models.UniqueConstraint(
                fields=("source", "type", "target"),
                name="unique_typed_relation",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.source_id} —{self.type_id}→ {self.target_id}"
