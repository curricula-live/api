# Agent instructions

## Scope

This repository is the Django API and administration surface for the curricula.live knowledge graph.

## Invariants

- PostgreSQL/Supabase is the target database. Do not replace it with SQLite-specific behavior.
- Preserve the existing `concept` and `relation` table names and UUID primary keys.
- Preserve relation foreign-key column names `source` and `target`.
- Relation predicates are extensible lowercase snake_case strings, not a closed enum.
- Public graph responses must remain bounded; do not return the entire graph by default.
- The SQL workbench must remain superuser-only, single-statement, timeout-bounded, and read-only unless write mode is explicitly confirmed.
- Never commit database credentials, service-role keys, or production secrets.

## Validation

Run before proposing changes:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
pytest
```

CI provisions PostgreSQL 17 and applies the real migrations.

## Preferred changes

- Add tests with every behavior change.
- Keep API and admin graph filtering logic in `graph/services.py` so both surfaces behave consistently.
- Use Django JSON serialization helpers in templates; never inject Python representations with `|safe`.
