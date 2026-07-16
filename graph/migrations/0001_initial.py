from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="Concept",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=160, unique=True)),
                ("label", models.CharField(max_length=240)),
                ("description", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "concept", "ordering": ["slug"]},
        ),
        migrations.CreateModel(
            name="Relation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("type", models.CharField(max_length=64)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("source", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="outgoing_relations", to="graph.concept")),
                ("target", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="incoming_relations", to="graph.concept")),
            ],
            options={"db_table": "relation"},
        ),
        migrations.AddConstraint(model_name="relation", constraint=models.UniqueConstraint(fields=("source", "target", "type"), name="unique_typed_relation")),
        migrations.AddIndex(model_name="relation", index=models.Index(fields=["source", "type"], name="relation_source__29a8a3_idx")),
        migrations.AddIndex(model_name="relation", index=models.Index(fields=["target", "type"], name="relation_target__1f4fa7_idx")),
    ]
