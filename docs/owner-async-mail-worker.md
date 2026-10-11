# Owner passwordless mail outbox — staging-only implementation

Depends on **data#22** (operational PostgreSQL migration 0003) and **api#53** (durable request throttling). This branch is intentionally stacked on api#53 and must not be independently deployed. No auth feature, SMTP credential or owner migration has been activated.

## Secret-free durable queue

- The HTTP challenge is issued in a database transaction with an outbox record tied to a random UUID. PostgreSQL stores **only** the challenge's purpose-separated digest and the UUID, never the raw bearer or complete email link.
- The worker derives a URL-safe 256-bit opaque challenge token with a *separate* private HMAC key (\`OWNER_EMAIL_TOKEN_KEY\`). The derivation binds the key to the UUID and a domain-separation label. The recovered token's digest MUST match the persisted challenge digest before mailing.
- Rotating/removing that key invalidates old undelivered items; mismatched entries are discarded. Rotation requires planning so pending emails aren't lost.
- A worker row is leased using \`FOR UPDATE OF o SKIP LOCKED\` and a 90-second lease. Sending occurs **outside** the transaction. Expired, already-used, inactive-owner and key-mismatched entries are discarded.
- Failures result in a bounded exponential retry, at most five tries and never beyond challenge expiry. Only the holder of the current lease can finalize the row. At-least-once delivery may create duplicate email messages; *redemption remains one-use*.
- No exception text, email address, challenge token, message content, or SMTP error is printed by the dispatcher. Operational metrics and alerting remain a release requirement.

## Explicit staging-only execution

The Django management command is \`python manage.py dispatch_owner_mail --limit 5 --confirm SEND-STAGING-OWNER-MAIL\`.

It refuses to run unless all conditions hold:
- \`APP_ENV=staging\` and \`IS_PRODUCTION=False\`
- \`OWNER_ASYNC_MAIL_ENABLED=true\`
- \`OWNER_EMAIL_WORKER_ENABLED=true\`
- \`OWNER_EMAIL_TOKEN_KEY\` is an independent **random** secret of at least 32 bytes
- \`OWNER_LOGIN_SENDER\` is set, and the link target passes the existing strict allowlist
- \`EMAIL_TIMEOUT\` is positive and at most 15 seconds

The HTTP route still requires its separate BFF, rate-limit and owner-auth flags, and is **hard-blocked in production**. The staging worker does not launch automatically or on a schedule. No staging or production database changes were made when the code was committed.

## Validation

Unit tests prove HMAC derivation stability, purpose separation and weak-key refusal. Disposable PostgreSQL integration tests exercise challenge+outbox atomic creation, recoverability without plaintext DB storage, mocked SMTP delivery, retry/backoff, expiry, key rotation and one-use redemption.

Remaining release gates:
1. Review/merge the data-owned migration and stacked API dependencies, then rehearse migrations only on isolated staging PostgreSQL.
2. Validate against a real staging deployment and an approved email provider using test recipient/sender, with message delivery and failure telemetry.
3. Implement real operating procedures: bounded scheduling, stale-job cleanup, key rotation/recovery, privileged worker isolation, provider credentials, sender/domain verification and rate-limit monitoring.
4. Perform neutral-response timing analysis and shared source/IP throttling before any production activation.
5. Review cross-repository BFF cookies, CSRF, external TLS and API authorization end-to-end.

This is feature work, **not** a production release or authorization to send mail.
