# Generated for the semantic publication vertical slice.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="SemanticPublicationSnapshot",
            fields=[
                ("snapshot_id", models.CharField(max_length=80, primary_key=True, serialize=False)),
                ("schema_version", models.CharField(max_length=40)),
                ("policy_version", models.CharField(max_length=80)),
                (
                    "canonicalization_version",
                    models.CharField(default="canonical-json-v1", max_length=40),
                ),
                ("content_hash", models.CharField(max_length=64)),
                ("manifest", models.JSONField()),
                ("published_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "semantic_publication_snapshot",
                "ordering": ("snapshot_id",),
            },
        ),
        migrations.CreateModel(
            name="SemanticSnapshotConcept",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.TextField()),
                (
                    "snapshot",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="concept_memberships",
                        to="core.semanticpublicationsnapshot",
                    ),
                ),
            ],
            options={
                "db_table": "semantic_snapshot_concept",
                "ordering": ("slug",),
            },
        ),
        migrations.CreateModel(
            name="SemanticSnapshotEdge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_relation_id", models.UUIDField()),
                ("source_slug", models.TextField()),
                ("relation_type", models.TextField()),
                ("target_slug", models.TextField()),
                ("scope", models.JSONField(default=dict)),
                ("evidence", models.JSONField(default=list)),
                (
                    "snapshot",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="edges",
                        to="core.semanticpublicationsnapshot",
                    ),
                ),
            ],
            options={
                "db_table": "semantic_snapshot_edge",
                "ordering": ("source_slug", "relation_type", "target_slug", "source_relation_id"),
            },
        ),
        migrations.AddConstraint(
            model_name="semanticsnapshotconcept",
            constraint=models.UniqueConstraint(
                fields=("snapshot", "slug"),
                name="unique_semantic_snapshot_concept",
            ),
        ),
        migrations.AddConstraint(
            model_name="semanticsnapshotedge",
            constraint=models.UniqueConstraint(
                fields=("snapshot", "source_relation_id"),
                name="unique_semantic_snapshot_source_relation",
            ),
        ),
        migrations.AddConstraint(
            model_name="semanticsnapshotedge",
            constraint=models.UniqueConstraint(
                fields=("snapshot", "source_slug", "relation_type", "target_slug"),
                name="unique_semantic_snapshot_edge",
            ),
        ),
    ]
