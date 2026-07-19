import uuid

import django.db.models.deletion
import graph.models
from django.db import migrations, models

SCHEMA_SQL = """
create extension if not exists pgcrypto;

create table if not exists concept (
    id uuid primary key default gen_random_uuid(),
    slug text not null unique
);

create table if not exists relation (
    id uuid primary key default gen_random_uuid(),
    source uuid not null references concept(id) on update cascade on delete cascade,
    target uuid not null references concept(id) on update cascade on delete cascade,
    type text not null
);

alter table concept add column if not exists label text;
update concept set label = slug where label is null;
alter table concept alter column label set not null;
alter table concept add column if not exists description text not null default '';
alter table concept add column if not exists metadata jsonb not null default '{}'::jsonb;
alter table concept add column if not exists created_at timestamptz not null default now();
alter table concept add column if not exists updated_at timestamptz not null default now();

alter table relation add column if not exists metadata jsonb not null default '{}'::jsonb;
alter table relation add column if not exists created_at timestamptz not null default now();
alter table relation add column if not exists updated_at timestamptz not null default now();

do $$
begin
    if not exists (
        select 1 from pg_constraint
        where conrelid = 'relation'::regclass
          and conname = 'unique_typed_relation'
    ) then
        if exists (
            select 1 from pg_class
            where relkind = 'i' and relname = 'unique_typed_relation'
        ) then
            alter table relation add constraint unique_typed_relation
                unique using index unique_typed_relation;
        else
            alter table relation add constraint unique_typed_relation
                unique (source, target, type);
        end if;
    end if;
end $$;
create index if not exists relation_source_type_idx
    on relation(source, type);
create index if not exists relation_target_type_idx
    on relation(target, type);

alter table concept enable row level security;
alter table relation enable row level security;
"""


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    SCHEMA_SQL,
                    reverse_sql=migrations.RunSQL.noop,
                )
            ],
            state_operations=[
                migrations.CreateModel(
                    name="Concept",
                    fields=[
                        (
                            "id",
                            models.UUIDField(
                                default=uuid.uuid4,
                                editable=False,
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
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
                        (
                            "id",
                            models.UUIDField(
                                default=uuid.uuid4,
                                editable=False,
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        (
                            "type",
                            models.SlugField(
                                help_text=(
                                    "Extensible relation predicate, for example "
                                    "prerequisite_of or part_of."
                                ),
                                max_length=64,
                                validators=[graph.models.validate_relation_type],
                            ),
                        ),
                        ("metadata", models.JSONField(blank=True, default=dict)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "source",
                            models.ForeignKey(
                                db_column="source",
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="outgoing_relations",
                                to="graph.concept",
                            ),
                        ),
                        (
                            "target",
                            models.ForeignKey(
                                db_column="target",
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="incoming_relations",
                                to="graph.concept",
                            ),
                        ),
                    ],
                    options={"db_table": "relation"},
                ),
                migrations.AddConstraint(
                    model_name="relation",
                    constraint=models.UniqueConstraint(
                        fields=("source", "target", "type"),
                        name="unique_typed_relation",
                    ),
                ),
                migrations.AddIndex(
                    model_name="relation",
                    index=models.Index(
                        fields=["source", "type"],
                        name="relation_source_type_idx",
                    ),
                ),
                migrations.AddIndex(
                    model_name="relation",
                    index=models.Index(
                        fields=["target", "type"],
                        name="relation_target_type_idx",
                    ),
                ),
            ],
        )
    ]
