# curricula.live API

**Django and PostgreSQL backend for a curriculum knowledge platform that models concepts, relationships and learning paths.**

<p align="center">
  <img src="docs/architecture.svg" alt="curricula.live API architecture" width="100%">
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
  <img alt="Django" src="https://img.shields.io/badge/Django-5.2-0C4B33?logo=django&logoColor=white">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-provider%20neutral-4169E1?logo=postgresql&logoColor=white">
  <img alt="Package manager" src="https://img.shields.io/badge/package%20manager-uv-6B5DD3">
  <img alt="Tests" src="https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white">
</p>

## Purpose

`curricula.live` is being developed around a simple question:

> **What must a learner understand, and what should come before it?**

The platform represents curriculum content as a graph of concepts and typed relationships. This repository is the Django backend API, with environment-based configuration, PostgreSQL connectivity, administration, graph read endpoints, health checks and isolated tests.

## Current capabilities

- Django 5.2 on Python 3.12.
- PostgreSQL connection through provider-neutral `DATABASE_URL`.
- Compatibility settings for PostgreSQL poolers.
- Django admin and built-in authentication foundation.
- JSON health endpoint at `/health/`.
- Read endpoints for concepts, relations, relation types, neighbourhoods and prerequisite traversal.
- Explicit cross-origin access for configured curricula.live frontend origins; no wildcard CORS.
- Environment configuration through `django-environ`.
- Dependency and virtual-environment management through `uv`.
- `pytest` and `pytest-django` test infrastructure.
- In-memory SQLite test database isolated from development and deployed PostgreSQL data.
- WSGI and ASGI entry points for deployment flexibility.
- Vercel-compatible production settings with exact preview-host handling.

## Current HTTP surface

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health/` | Service readiness and smoke-check response |
| varies | `/admin/` | Django administrative interface |
| `GET` | `/api/concepts/` | List concepts |
| `GET` | `/api/concepts/<slug>/` | Read a concept |
| `GET` | `/api/concepts/<slug>/neighborhood/` | Read incoming/outgoing graph neighbourhood |
| `GET` | `/api/concepts/<slug>/prerequisites/` | Bounded prerequisite traversal |
| `GET` | `/api/relations/` | List/filter relations |
| `GET` | `/api/relations/<uuid>/` | Read a relation |
| `GET` | `/api/relation-types/` | List relation types |

Example health response:

```json
{
  "status": "ok",
  "service": "curricula.live api"
}
```

The `/api/` prefix is the current development contract. Public API versioning is intentionally tracked separately from deployment infrastructure.

## Architecture

```mermaid
flowchart LR
    Web[curricula.live web client]
    Admin[Django admin user]
    Monitor[Health monitor]
    Django[Django 5.2 API]
    Core[core application]
    DB[(Managed PostgreSQL)]
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
    CORS[DJANGO_CORS_ALLOWED_ORIGINS]
    URL[DATABASE_URL]
    Psycopg[psycopg 3]
    Postgres[(PostgreSQL)]

    Env --> Settings
    Settings --> Secret
    Settings --> Debug
    Settings --> Hosts
    Settings --> CORS
    Settings --> URL
    URL --> Psycopg
    Psycopg --> Postgres
```

## Repository structure

```text
api/
├── config/
│   ├── settings.py       # Runtime and production configuration
│   ├── test_settings.py  # Isolated test environment
│   ├── urls.py           # Root URL routing
│   ├── asgi.py           # ASGI application entry point
│   └── wsgi.py           # WSGI application entry point
├── core/
│   ├── admin.py          # Domain admin configuration
│   ├── middleware.py     # Narrow CORS policy
│   ├── models.py         # Unmanaged curriculum read models
│   ├── urls.py           # API routes
│   ├── views.py          # Health and graph read endpoints
│   └── migrations/
├── tests/                # API, graph, admin and deployment-facing tests
├── docs/
│   ├── architecture.svg
│   └── deployment.md     # Vercel production runbook
├── .env.example          # Local/environment configuration template
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
- A PostgreSQL connection string exposed as `DATABASE_URL`.

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
DJANGO_CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require
```

Any PostgreSQL provider can be used. Never commit `.env`.

### 5. Verify the Django configuration

```bash
uv run python manage.py check
```

### 6. Apply migrations

```bash
uv run python manage.py migrate
```

The curriculum graph tables are currently read through unmanaged models. Django migrations still manage Django's built-in authentication, administration, session and content-type tables.

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

The suite covers health, domain read models, concepts, relations, relation types, neighbourhoods, prerequisite traversal, admin configuration and CORS behavior.

### Why tests use SQLite

`pytest.ini` loads `config.test_settings`. That module overrides:

```text
DATABASE_URL=sqlite://:memory:
```

before importing normal settings. Consequently:

- tests cannot accidentally modify a developer or deployed PostgreSQL database;
- the suite does not require network access;
- test state is temporary and discarded after the process exits;
- health and application tests remain fast.

Database-specific behaviour still requires separate PostgreSQL integration tests.

## Database configuration

The application requires `DATABASE_URL`:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE
```

For hosted PostgreSQL requiring TLS:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE?sslmode=require
```

When the configured engine is PostgreSQL, settings apply:

- `CONN_MAX_AGE = 0`;
- disabled server-side cursors;
- `prepare_threshold = None`.

These choices avoid connection-state problems with poolers and serverless instances. They trade some persistent-connection optimisation for predictable provider compatibility.

The API must not import provider-specific database SDKs. Moving from one managed PostgreSQL provider to another should primarily be a `DATABASE_URL` and compatibility-validation change.

## Environment variables

| Variable | Required | Example | Description |
|---|---:|---|---|
| `DJANGO_SECRET_KEY` | yes | generated random value | Cryptographic signing secret |
| `DJANGO_DEBUG` | no | `false` | Enables Django debug mode; defaults to `false` |
| `DJANGO_ALLOWED_HOSTS` | no | `api.curricula.live` | Comma-separated accepted hostnames |
| `DJANGO_CORS_ALLOWED_ORIGINS` | no | `https://curricula.live` | Browser origins allowed to call the read API |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | no | `https://api.curricula.live` | Trusted origins for Django CSRF checks |
| `DATABASE_URL` | yes | PostgreSQL URL | Database connection |
| `APP_ENV` | no | `production` | Enables production-safe defaults when set to `production` |
| `DJANGO_SECURE_SSL_REDIRECT` | no | `true` | Override HTTPS redirect behavior |
| `DJANGO_SESSION_COOKIE_SECURE` | no | `true` | Override secure session-cookie behavior |
| `DJANGO_CSRF_COOKIE_SECURE` | no | `true` | Override secure CSRF-cookie behavior |
| `DJANGO_SECURE_HSTS_SECONDS` | no | `31536000` | Override HSTS lifetime |
| `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` | no | `false` | Opt into HSTS for subdomains |
| `DJANGO_SECURE_HSTS_PRELOAD` | no | `false` | Opt into HSTS preload signaling |

When Vercel supplies `VERCEL_URL` or `VERCEL_PROJECT_PRODUCTION_URL`, their exact hostnames are accepted automatically for preview/production deployments. The app does not allow all `*.vercel.app` hosts.

## Common commands

| Task | Command |
|---|---|
| Install/synchronise dependencies | `uv sync --dev` |
| Run Django checks | `uv run python manage.py check` |
| Run deployment checks | `uv run python manage.py check --deploy` |
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

## Deployment

The current production target is **Vercel** at `api.curricula.live`, with the frontend deployed independently and PostgreSQL reached through `DATABASE_URL`.

Vercel's Django integration detects `manage.py`, WSGI and Django staticfiles, so this repository intentionally does not carry a legacy Python builder or catch-all routing configuration.

Production requires at minimum:

```dotenv
APP_ENV=production
DJANGO_SECRET_KEY=<generated secret>
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=api.curricula.live
DATABASE_URL=<managed PostgreSQL URL>
DJANGO_CORS_ALLOWED_ORIGINS=https://curricula.live,https://www.curricula.live
DJANGO_CSRF_TRUSTED_ORIGINS=https://api.curricula.live,https://curricula.live,https://www.curricula.live
```

Production migrations are **not** run automatically on preview deployments. They are a controlled release step so previews cannot mutate a shared production database.

See [`docs/deployment.md`](docs/deployment.md) for the Vercel project setup, custom-domain/DNS procedure, migration flow, static/admin verification, security settings and migration-away strategy.

CI also runs:

```bash
uv run python manage.py check --deploy
```

against a production-shaped configuration.

## Known limitations

- PostgreSQL-specific behaviour is not yet covered by a dedicated integration-test environment.
- The public API contract is not versioned yet; `/api/` remains the current development prefix.
- API authentication and write authorization have not yet been introduced.
- There is no generated OpenAPI schema yet.
- Production deployment still requires account-level Vercel environment variables and custom-domain configuration outside the repository.

## Contributing

Keep each contribution focused on one logical change. A typical workflow:

```bash
git checkout dev
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

The `curricula-live` organisation separates application concerns into focused repositories. This API works alongside repositories for the web client, canonical data and organisation-level documentation.

## License

No explicit licence is currently included. Unless a licence is added, the repository remains under the copyright holder’s default rights.
