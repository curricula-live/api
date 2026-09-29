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

    metadata = models.JSONField(default=dict)

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


class SemanticPublicationSnapshot(models.Model):
    snapshot_id = models.CharField(primary_key=True, max_length=80)
    schema_version = models.CharField(max_length=40)
    policy_version = models.CharField(max_length=80)
    canonicalization_version = models.CharField(max_length=40, default="canonical-json-v1")
    content_hash = models.CharField(max_length=64)
    manifest = models.JSONField()
    published_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "semantic_publication_snapshot"
        ordering = ("snapshot_id",)

    def __str__(self) -> str:
        return self.snapshot_id


class SemanticSnapshotConcept(models.Model):
    snapshot = models.ForeignKey(
        SemanticPublicationSnapshot,
        on_delete=models.PROTECT,
        related_name="concept_memberships",
    )
    slug = models.TextField()

    class Meta:
        db_table = "semantic_snapshot_concept"
        constraints = [
            models.UniqueConstraint(
                fields=("snapshot", "slug"),
                name="unique_semantic_snapshot_concept",
            ),
        ]
        ordering = ("slug",)


class SemanticSnapshotEdge(models.Model):
    snapshot = models.ForeignKey(
        SemanticPublicationSnapshot,
        on_delete=models.PROTECT,
        related_name="edges",
    )
    source_relation_id = models.UUIDField()
    source_slug = models.TextField()
    relation_type = models.TextField()
    target_slug = models.TextField()
    scope = models.JSONField(default=dict)
    evidence = models.JSONField(default=list)

    class Meta:
        db_table = "semantic_snapshot_edge"
        constraints = [
            models.UniqueConstraint(
                fields=("snapshot", "source_relation_id"),
                name="unique_semantic_snapshot_source_relation",
            ),
            models.UniqueConstraint(
                fields=("snapshot", "source_slug", "relation_type", "target_slug"),
                name="unique_semantic_snapshot_edge",
            ),
        ]
        ordering = ("source_slug", "relation_type", "target_slug", "source_relation_id")
