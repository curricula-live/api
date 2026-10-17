# Opt-in v2 concept preview (not production)

The v2 Git source is in \`curricula-live/data/dev\`; the Django production API
still reads legacy \`public.concept\` via its v1 interface.

This draft PR adds read-only, **disabled-by-default** staging routes:

- \`GET /v2-preview/concepts/by-slug/{slug}/\`
- \`GET /v2-preview/concepts/{uuid}/\`

Set \`V2_READ_PREVIEW_ENABLED=true\` only in an explicitly isolated staging
environment where the data-owned \`knowledge.concept\` PostgreSQL schema is
installed and populated. The flag is ignored when \`APP_ENV=production\`.

Responses deliberately say \`release_verified: false\`. The response is not
a publication certificate, definition or academic review verdict.
Unknown concepts return 404; missing staging schema returns 503 with no SQL
details. No legacy fallback is allowed. All public \`/v1/\` routes are untouched.

**Before stable v2 endpoints:** perform the explicit read-only PostgreSQL
parity gate in data PR #19, add immutable release identity in data #10,
coordinate published schema cutover in api #21, and add version-pinned API
tests. Do not enable a production v2 read route until those gates pass.
