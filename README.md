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

## Deployment

Vercel runs `config.wsgi:application` as a serverless Python function and
collects static assets during the build. Do not use the deployment filesystem
for persistent data or run migrations during function startup.

Configure these separately for Preview and Production:

- `DATABASE_URL` (required): PostgreSQL connection URL. Preview must use a
  staging database or a database role that cannot modify production data.
- `DJANGO_SECRET_KEY` (required): a distinct, random value per environment.
- `DJANGO_DEBUG` (required): `false` outside local development.
- `DJANGO_ALLOWED_HOSTS` (required): comma-separated deployment hostnames.
- `DJANGO_CSRF_TRUSTED_ORIGINS` (required for admin/API browser writes):
  comma-separated `https://` origins.
- `DB_SSL_REQUIRE` (required for Supabase): `true`.

Run migrations as an explicit, reviewed deployment operation. The current
initial migration adopts and extends the graph tables, so it must not be run
against production until its SQL has been compared with the real Supabase
schema and tested on a staging clone. Create the first administrator with
`python manage.py createsuperuser` from a trusted one-off environment connected
to the intended database.
