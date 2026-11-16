"""Build a disposable SQLite preview from curricula-live/data's canonical JSONL.

This tool is for local integration tests only. It NEVER reads the configured
DATABASE_URL or connects to PostgreSQL. It refuses any path outside the OS temp
directory. No file is replaced unless --replace is explicitly supplied.

Example:
  python tests/tools/bootstrap_data_sqlite.py \
      --data-root ../data --output /tmp/curricula-concept-preview.sqlite3
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument(
        "--output", type=Path,
        default=Path(tempfile.gettempdir()) / "curricula-concept-preview.sqlite3",
    )
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    temp_root = Path(tempfile.gettempdir()).resolve()
    output = args.output.resolve()
    if output.suffix != ".sqlite3" or not output.is_relative_to(temp_root) or output == temp_root:
        parser.error("SQLite output must end in .sqlite3 and be inside the OS temp directory")
    if output.exists() and not args.replace:
        parser.error(f"Refusing to overwrite {output} without --replace")
    if output.is_symlink():
        parser.error("Refusing to follow an existing SQLite symlink")
    data_root = args.data_root.expanduser().resolve()
    if not (data_root / "knowledge" / "concepts.jsonl").is_file():
        parser.error("Provide an existing canonical data repo containing knowledge/concepts.jsonl")

    concepts = read_jsonl(data_root / "knowledge" / "concepts.jsonl")
    predicates = read_jsonl(data_root / "knowledge" / "predicates.jsonl")
    statements = read_jsonl(data_root / "knowledge" / "statements.jsonl")
    slugs = {concept["id"]: concept["slug"] for concept in concepts}
    if len(slugs) != len(concepts):
        parser.error("Duplicate concept identities")
    relation_rows = []
    for row in statements:
        if row["subject"]["kind"] != "concept" or row["object"]["kind"] != "concept":
            continue  # The v1 legacy API only models concept-to-concept edges.
        if row["subject"]["id"] not in slugs or row["object"]["id"] not in slugs:
            parser.error("Unresolved statement identity")
        relation_rows.append(row)

    if output.exists():
        output.unlink()

    # Isolated runtime: no deployed secret, host or database setting is read.
    os.environ["DATABASE_URL"] = f"sqlite:///{output}"
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
    os.environ["DJANGO_SECRET_KEY"] = "LOCAL-DISPOSABLE-TEST-ONLY"
    os.environ["APP_ENV"] = "development"
    os.environ["DJANGO_DEBUG"] = "0"
    os.environ["DJANGO_ALLOWED_HOSTS"] = "127.0.0.1,localhost,testserver"
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    import django
    django.setup()
    from django.db import connection, transaction
    from core.models import Concept, Relation, RelationType

    with connection.schema_editor() as editor:
        for model in (Concept, RelationType, Relation):
            editor.create_model(model)

    with transaction.atomic():
        Concept.objects.bulk_create([Concept(slug=row["slug"]) for row in concepts])
        RelationType.objects.bulk_create([RelationType(slug=row["slug"]) for row in predicates])
        Relation.objects.bulk_create([
            Relation(
                id=row["id"],
                source_id=slugs[row["subject"]["id"]],
                type_id=row["predicate"],
                target_id=slugs[row["object"]["id"]],
            )
            for row in relation_rows
        ])

    print(f"Disposable file: {output}")
    print(
        f"Loaded {Concept.objects.count()} concepts, "
        f"{RelationType.objects.count()} predicates and "
        f"{Relation.objects.count()} directed relations"
    )
    print("Local-only. Contains provisional canonical data, not approved V2 source assertions.")


if __name__ == "__main__":
    main()
