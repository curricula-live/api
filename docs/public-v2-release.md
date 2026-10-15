# Published knowledge v2 and owner release gate

`/v2/concepts/` is an anonymous, bounded, UUID-based read contract. A concept
can be read by UUID at `/v2/concepts/<uuid>/`; its related statements are at
`/v2/concepts/<uuid>/statements/`. Collection and statement pages accept
`limit=1..100` and `offset=0..10000`; collection search accepts `q` up to 80
characters. Responses carry `knowledge-v2@1` and the stamped Git release
commit. Statements have explicit `unreviewed` and missing-evidence status.
The current corpus has no canonical definitions, scholarly references, or
ACM/CS2023/CSTA mappings. Endpoints do not claim otherwise. `/v1` remains
unchanged.

All `/v2` routes fail closed by default. They require
`PUBLIC_V2_ENABLED=true`, a 40-character `PUBLIC_V2_RELEASE_COMMIT`, and an
exact match with `knowledge.publication` in PostgreSQL. The data repository's
migration `0004_knowledge_release.sql` creates that marker. Its
`stamp_publication.py` command stamps only a clean canonical checkout after
an exact database readback. A subsequent canonical `publish.py apply` clears
the marker. The deployed API database role should have SELECT access to
published `knowledge` tables only; it must not have writer or `admin` schema
privileges beyond the separate owner-auth service needs. Use separate roles
when granting those capabilities.

Before a staging release, independently verify the v1→v2 parity against an
independently sourced legacy staging snapshot using the data repository's
read-only verifier. Apply reviewed knowledge and admin DDL to a non-production
target, publish a reviewed canonical commit there, verify, stamp, and set the
matching API commit. Test anonymous `/v2`, old `/v1`, owner auth, and direct
unauthorized access. The local demonstration is a Git-fed database and does
not satisfy independent parity.

Production owner POSTs require both owner feature flags, the exact HTTPS link
origin, a strong BFF secret, a durable rate-limit key, an independent email
token key, and the asynchronous mail worker. Production additionally requires
Django SMTP backend, `DJANGO_EMAIL_HOST_USER`, `DJANGO_EMAIL_HOST_PASSWORD`, a
non-local `DJANGO_EMAIL_HOST`, and exactly one of `DJANGO_EMAIL_USE_TLS` or
`DJANGO_EMAIL_USE_SSL`. Run a persistent worker with
`dispatch_owner_mail --confirm SEND-PRODUCTION-OWNER-MAIL` on a bounded
schedule; run `maintain_owner_mail --confirm MAINTAIN-PRODUCTION-OWNER-MAIL`
separately. HTTP requests only enqueue mail. A serverless API deployment alone
cannot dispatch it. Confirm actual external email delivery on staging before
production approval. SMTP secrets belong in the deployment secret store.

For production approval, review the data, API and admin commits together;
verify independently sourced parity and the published Git `main` corpus;
confirm database backup/rollback, least-privilege roles, worker scheduling,
HTTPS domains, secure cookies, SMTP delivery and browser access checks. Promote
`dev` to `main` through coordinated release PRs, then apply approved migrations
and publish only from data `main`. A release marker mismatch intentionally
returns 503; rollback the API flags or restore the previous verified database
snapshot and marker rather than serving preview or fixture data.
