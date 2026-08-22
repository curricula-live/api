# curricula.live API

**Django and PostgreSQL foundation for a curriculum knowledge platform that will model concepts, relationships and learning paths.**

<p align="center">
  <img src="docs/architecture.svg" alt="curricula.live API architecture" width="100%">
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
  <img alt="Django" src="https://img.shields.io/badge/Django-5.2-0C4B33?logo=django&logoColor=white">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-Supabase%20compatible-4169E1?logo=postgresql&logoColor=white">
  <img alt="Package manager" src="https://img.shields.io/badge/package%20manager-uv-6B5DD3">
  <img alt="Tests" src="https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white">
  <img alt="Status" src="https://img.shields.io/badge/status-foundation-E1A95F">
</p>

## Purpose

`curricula.live` is being developed around a simple question:

> **What must a learner understand, and what should come before it?**

The wider platform is intended to represent curriculum content as a graph of concepts and typed relationships. This repository is the backend API foundation: a deliberately small Django service with environment-based configuration, PostgreSQL connectivity, Django administration, a health endpoint and an isolated test setup.

The current codebase is not yet the complete curriculum API. It establishes the infrastructure on which concept, relation, curriculum and recommendation features can be added through focused changes.

## Current capabilities

- Django 5.2 project running on Python 3.12.
- PostgreSQL connection through `DATABASE_URL`.
- Compatibility settings for Supabase/PostgreSQL poolers.
- Django admin and built-in authentication foundation.
- JSON health endpoint at `/health/`.
- Environment configuration through `django-environ`.
- Dependency and virtual-environment management through `uv`.
- `pytest` and `pytest-django` test infrastructure.
- In-memory SQLite test database isolated from development and deployed PostgreSQL data.
- WSGI and ASGI entry points for deployment flexibility.

## Current HTTP surface

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health/` | Service readiness and smoke-check response |
| varies | `/admin/` | Django administrative interface |

Example health response:

```json
{
  "status": "ok",
  "service": "curricula.live api"
}
```

Domain endpoints for curriculum concepts and relationships have not yet been added to this Django foundation.

## Architecture

```mermaid
flowchart LR
    Web[Future curricula.live web client]
    Admin[Django admin user]
    Monitor[Health monitor]
    Django[Django 5.2 API]
    Core[core application]
    DB[(PostgreSQL / Supabase)]
    Tests[pytest-django]
    SQLite[(In-memory SQLite)]

    Web --> Django
    Admin --> Django
    Monitor -->|GET /health/| Django
    Django --> Core
    Django --> DB
    Tests --> Core
    Tests --> SQLite
```

### Configuration path

```mermaid
flowchart TD
    Env[.env or deployment environment]
    Settings[config/settings.py]
    Secret[DJANGO_SECRET_KEY]
    Debug[DJANGO_DEBUG]
    Hosts[DJANGO_ALLOWED_HOSTS]
    URL[DATABASE_URL]
    Psycopg[psycopg 3]
    Postgres[(PostgreSQL)]

    Env --> Settings
    Settings --> Secret
    Settings --> Debug
    Settings --> Hosts
    Settings --> URL
    URL --> Psycopg
    Psycopg --> Postgres
```

## Repository structure

```text
api/
├── config/
│   ├── settings.py       # Runtime configuration
│   ├── test_settings.py  # Isolated test environment
│   ├── urls.py           # Root URL routing
│   ├── asgi.py           # ASGI application entry point
│   └── wsgi.py           # WSGI application entry point
├── core/
│   ├── apps.py
│   ├── views.py          # Health endpoint
│   └── migrations/
├── tests/
│   └── test_health.py    # Health-endpoint contract test
├── docs/
│   └── architecture.svg
├── .env.example          # Local configuration template
├── .python-version       # Python runtime selection
├── manage.py             # Django management command entry point
├── pyproject.toml        # Project and dependency declaration
├── pytest.ini            # pytest-django configuration
├── uv.lock               # Reproducible dependency lockfile
└── README.md
```

## Requirements

- Python 3.12 or newer within the supported project range.
- [`uv`](https://docs.astral.sh/uv/) for dependency and environment management.
- PostgreSQL for normal development and deployment.
- A database connection string, such as a Supabase Session Pooler URL.

## Local setup

### 1. Clone the repository

```bash
git clone https://github.com/curricula-live/api.git
cd api
```

### 2. Install `uv`

Linux and macOS:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Restart the terminal if `uv` is not immediately available on `PATH`.

### 3. Synchronise dependencies

```bash
uv sync --dev
```

This creates or updates the local virtual environment from `pyproject.toml` and `uv.lock`.

The main runtime dependencies are:

- Django;
- `django-environ`;
- psycopg 3 with its binary distribution.

The development dependency group adds:

- pytest;
- pytest-django.

### 4. Create local environment configuration

Linux, macOS or Git Bash:

```bash
cp .env.example .env
```

Windows Command Prompt:

```bat
copy .env.example .env
```

Generate a Django secret:

```bash
uv run python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Update `.env`:

```dotenv
APP_ENV=development
DJANGO_SECRET_KEY=replace-with-generated-secret
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,testserver
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require
```

For Supabase local development, use the project’s **Session Pooler** connection string and replace the password placeholder. Never commit `.env`.

### 5. Verify the Django configuration

```bash
uv run python manage.py check
```

### 6. Apply migrations

```bash
uv run python manage.py migrate
```

At this stage, migrations primarily create Django’s built-in authentication, administration, session and content-type tables.

### 7. Create an administrator

```bash
uv run python manage.py createsuperuser
```

### 8. Start the development server

```bash
uv run python manage.py runserver
```

Open:

- Health endpoint: `http://127.0.0.1:8000/health/`
- Admin interface: `http://127.0.0.1:8000/admin/`

## Test the service

### Browser or curl

```bash
curl http://127.0.0.1:8000/health/
```

Expected response:

```json
{"status":"ok","service":"curricula.live api"}
```

### Run the test suite

```bash
uv run pytest
```

The current suite verifies the status code and exact JSON contract of the health endpoint.

### Why tests use SQLite

`pytest.ini` loads `config.test_settings`. That module overrides:

```text
DATABASE_URL=sqlite://:memory:
```

before importing normal settings. Consequently:

- tests cannot accidentally modify the developer’s Supabase/PostgreSQL database;
- the suite does not require network access;
- test state is temporary and discarded after the process exits;
- health and application tests remain fast.

Database-specific behaviour still requires separate PostgreSQL integration tests when domain models and queries are introduced.

## Database configuration

The normal application requires `DATABASE_URL`:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE
```

For hosted PostgreSQL requiring TLS:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE?sslmode=require
```

When the configured engine is PostgreSQL, the settings currently apply:

- `CONN_MAX_AGE = 0`;
- disabled server-side cursors;
- `prepare_threshold = None`.

These choices avoid connection-state problems with transaction or session poolers, particularly during early Supabase-backed deployment work. They trade some persistent-connection optimisation for simpler pooler compatibility.

## Environment variables

| Variable | Required | Example | Description |
|---|---:|---|---|
| `DJANGO_SECRET_KEY` | yes | generated random value | Cryptographic signing secret |
| `DJANGO_DEBUG` | no | `true` | Enables Django debug mode; defaults to `false` |
| `DJANGO_ALLOWED_HOSTS` | no | `localhost,api.example.com` | Comma-separated accepted hostnames |
| `DATABASE_URL` | yes | PostgreSQL URL | Default database connection |
| `APP_ENV` | currently informational | `development` | Intended environment label |

The current `settings.py` assigns `SECRET_KEY` twice. The second assignment makes `DJANGO_SECRET_KEY` mandatory even though an earlier local default is present. This should be simplified in a focused configuration cleanup.

## Common commands

| Task | Command |
|---|---|
| Install/synchronise dependencies | `uv sync --dev` |
| Run Django checks | `uv run python manage.py check` |
| Create migrations | `uv run python manage.py makemigrations` |
| Apply migrations | `uv run python manage.py migrate` |
| Create administrator | `uv run python manage.py createsuperuser` |
| Start local server | `uv run python manage.py runserver` |
| Run tests | `uv run pytest` |
| Open Django shell | `uv run python manage.py shell` |

## Development principles

This backend is intentionally being built in small, reviewable increments:

1. Establish a stable Django and PostgreSQL foundation.
2. Add one domain concept at a time.
3. Keep environment configuration explicit.
4. Add tests with every behavioural change.
5. Preserve a clear boundary between canonical data, API behaviour and presentation.
6. Avoid hiding infrastructure decisions behind unexplained abstractions.

A future contributor should be able to understand why a dependency or setting exists without reconstructing the project’s history from pull requests.

## Planned domain model

The wider `curricula.live` system is expected to grow around entities such as:

- **Concept** — a unit of knowledge or skill;
- **Relation type** — the meaning of a connection, such as prerequisite or part-of;
- **Relation** — a directed, typed connection between concepts;
- **Curriculum** — an organised educational framework or programme;
- **Curriculum placement** — where a concept appears within a curriculum;
- **Resource** — a lesson, explanation, example, exercise or assessment;
- **Learning path** — an ordered or graph-derived route through concepts;
- **Evidence / provenance** — where curriculum claims and mappings originated.

These are design directions, not endpoints already implemented in this repository.

## Suggested API evolution

```mermaid
flowchart LR
    Foundation[Django foundation\nhealth + admin]
    Models[Concept and relation models]
    Admin[Domain-aware admin]
    ReadAPI[Read API]
    WriteAPI[Authenticated write API]
    Graph[Graph traversal and paths]
    Recommender[Learning recommendations]

    Foundation --> Models
    Models --> Admin
    Models --> ReadAPI
    ReadAPI --> WriteAPI
    ReadAPI --> Graph
    Graph --> Recommender
```

A maintainable sequence would be:

1. Formalise domain terminology and invariants.
2. Introduce models and migrations.
3. Expose useful administration workflows.
4. Add read-only endpoints.
5. Add authentication and write permissions.
6. Add graph queries and curriculum mappings.
7. Add recommendation logic only after source data and evaluation criteria are reliable.

## Deployment notes

Before deploying:

- set `DJANGO_DEBUG=false`;
- generate a unique `DJANGO_SECRET_KEY`;
- list every deployment hostname in `DJANGO_ALLOWED_HOSTS`;
- use a TLS-enabled PostgreSQL URL;
- run migrations as a controlled deployment step;
- configure static-file handling for the Django admin;
- add health monitoring for `/health/`;
- verify CSRF and trusted-origin settings when a browser frontend is connected;
- run `uv run python manage.py check --deploy`.

Example deployment check:

```bash
uv run python manage.py check --deploy
```

## Known limitations

- Only health and Django admin routes are currently exposed.
- Domain models and curriculum endpoints have not yet been implemented.
- `settings.py` contains a duplicate `SECRET_KEY` assignment.
- PostgreSQL integration is configured but not covered by the current SQLite test suite.
- Static-file serving for deployed admin pages is not yet documented in code.
- API authentication, authorisation and CORS strategy have not yet been introduced.
- There is no generated OpenAPI schema yet.
- Deployment configuration is intentionally still minimal.

## Contributing

Keep each contribution focused on one logical change. A typical workflow:

```bash
git checkout main
git pull
git checkout -b feat/descriptive-change-name
uv sync --dev
uv run pytest
```

Before opening a pull request:

```bash
uv run python manage.py check
uv run pytest
```

Document new environment variables, migrations, dependencies and operational assumptions in the same pull request that introduces them.

## Related repositories

The `curricula-live` organisation separates application concerns into focused repositories. This API is expected to work alongside repositories for the web client, canonical data and organisation-level documentation.

## License

No explicit licence is currently included. Unless a licence is added, the repository remains under the copyright holder’s default rights.
