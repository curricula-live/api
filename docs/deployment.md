# Vercel deployment runbook

The curricula.live API is deployed as an independent Django service. The web frontend and the PostgreSQL provider are separate concerns and can move independently.

## Target architecture

```text
curricula.live                api.curricula.live
     |                               |
 frontend host                    Vercel
                                     |
                                Django WSGI
                                     |
                                DATABASE_URL
                                     |
                           managed PostgreSQL
```

Vercel is the current compute target. PostgreSQL remains provider-neutral: the application only consumes `DATABASE_URL` and does not depend on Supabase-specific application APIs.

## Vercel project

Import `curricula-live/api` as its own Vercel project.

Vercel's Django support detects `manage.py`, the WSGI entry point in `config/wsgi.py`, and Django staticfiles. No legacy Python builder or catch-all `vercel.json` routing configuration is required.

Use `main` as the production branch once the current integration work is merged. Pull requests and integration branches should receive preview deployments through the Git integration.

## Public API routing

The dedicated API hostname already identifies the service, so the public contract does not add a redundant `/api/` namespace.

```text
https://api.curricula.live/
https://api.curricula.live/health/
https://api.curricula.live/v1/concepts/
https://api.curricula.live/v1/relations/
https://api.curricula.live/v1/relation-types/
```

`/` is a discovery endpoint that advertises the latest stable API version. Stable consumers select an explicit major version. Bare resource aliases such as `/concepts/` are not used, and `/api/...` is not part of the canonical public contract.

A future `/v2/` should be introduced only for genuinely breaking contract changes. Additive endpoints or compatible fields remain within the current major version.

## Production environment

Configure these variables in Vercel's Production environment:

```dotenv
APP_ENV=production
DJANGO_SECRET_KEY=<generated production secret>
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=api.curricula.live
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require
DJANGO_CORS_ALLOWED_ORIGINS=https://curricula.live,https://www.curricula.live
DJANGO_CSRF_TRUSTED_ORIGINS=https://api.curricula.live,https://curricula.live,https://www.curricula.live
```

Generate `DJANGO_SECRET_KEY` locally without committing it:

```bash
uv run python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

`VERCEL_URL` and `VERCEL_PROJECT_PRODUCTION_URL` are supplied by Vercel. Django adds their exact hostnames to `ALLOWED_HOSTS` and trusted CSRF origins automatically so preview deployments do not require a wildcard `*.vercel.app` host rule.

The production transport settings default to secure values when `APP_ENV=production`. They can be overridden through the documented `DJANGO_SECURE_*` variables only when there is a concrete operational reason.

## Static files and Django admin

`STATIC_ROOT` is defined as `staticfiles/`, while `django.contrib.staticfiles` remains installed. Vercel's Django integration detects the staticfiles configuration as part of the framework build, so the admin does not require a custom Python builder.

After deployment, verify that both the admin page and one of its static assets return successfully. If Vercel's framework behavior changes, capture that as a deployment regression rather than introducing legacy routing pre-emptively.

## Database migrations

Do **not** run production migrations automatically on every preview deployment. Preview deployments can otherwise mutate the same database as production.

The controlled migration flow is:

1. Review migrations in the branch/PR.
2. Merge the application change.
3. Pull or run the Vercel Production environment locally.
4. Inspect the migration plan.
5. Apply migrations deliberately.
6. Verify `/health/` and the affected API endpoint.

With a Vercel project linked locally:

```bash
vercel env run -e production -- uv run python manage.py showmigrations --plan
vercel env run -e production -- uv run python manage.py migrate
```

If the PostgreSQL provider later supports isolated database branches for previews, preview migrations can be reconsidered without changing Django's database configuration contract.

## Custom domain

Add `api.curricula.live` to the API Vercel project. Configure the DNS record exactly as Vercel reports for the domain, then wait for Vercel to verify ownership and issue TLS.

Do not point the frontend project at this hostname; `api.curricula.live` belongs only to the Django API service.

## Verification

Run the production deployment check before release:

```bash
APP_ENV=production \
DJANGO_SECRET_KEY='replace-with-a-long-generated-secret' \
DJANGO_DEBUG=false \
DJANGO_ALLOWED_HOSTS=api.curricula.live \
DATABASE_URL='sqlite://:memory:' \
uv run python manage.py check --deploy
```

After the custom domain is active:

```bash
curl -i https://api.curricula.live/
curl -i https://api.curricula.live/health/
curl -i -H 'Origin: https://curricula.live' https://api.curricula.live/v1/concepts/
```

Expected discovery payload:

```json
{"service":"curricula.live API","latest_version":"v1","versions":{"v1":"/v1/"}}
```

Expected health payload:

```json
{"status":"ok","service":"curricula.live api"}
```

The versioned API request should include:

```text
Access-Control-Allow-Origin: https://curricula.live
Vary: Origin
```

An unconfigured origin must not receive `Access-Control-Allow-Origin`.

## Moving away from Vercel or Supabase

The deployment-specific assumptions are intentionally shallow:

- Django exposes normal WSGI and ASGI entry points.
- PostgreSQL is configured through `DATABASE_URL`.
- Vercel system hostnames are additive rather than required.
- no application code imports a database-provider SDK;
- no Vercel-specific routing file is required.

A future move to AWS ECS/Fargate, Azure Container Apps, Railway, Fly.io, or another conventional runtime should therefore be primarily an infrastructure change. A future PostgreSQL migration should primarily require changing `DATABASE_URL` and validating PostgreSQL compatibility.
