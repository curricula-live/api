# curricula.live API

Django and Django REST Framework service for editing and serving the curricula.live concept graph stored in PostgreSQL/Supabase.

## Features

- REST resources for concepts and typed relations
- bounded graph endpoint with text and relation-type filters
- Django admin tables with search and relation autocomplete
- graph explorer at `/admin/graph/`
- superuser-only SQL workbench at `/admin/sql/`

## Local setup

The project targets PostgreSQL because its initial migration adopts the existing Supabase UUID schema.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Export the variables from `.env`, then run:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## API

- `GET /api/health/`
- `GET /api/concepts/`
- `GET /api/relations/`
- `GET /api/graph/?q=queue&type=prerequisite_of&limit=250`

Anonymous clients may read. Authenticated Django users may write through the REST API according to their permissions.

## Tests

```bash
pytest
```

The GitHub Actions workflow provisions PostgreSQL 17, applies migrations, checks for migration drift, and runs the test suite.
