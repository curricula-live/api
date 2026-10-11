# Owner passwordless lifecycle — internal service contract

This change implements **internal service functions**, not public authentication routes. The Django API and Next.js administration app remain fail-closed until the HTTP/email/cookie integration is reviewed and tested.

## Invariants

- The unique active `owner` principal is authoritative in the data-owned `admin.owner_principal` PostgreSQL schema; the client cannot assert a role.
- `issue_challenge(email)` normalizes the identity, locks the active owner row, enforces a per-owner one-minute issue cooldown, and stores **only** a purpose-separated SHA-256 digest of a cryptographically random opaque token. The email challenge expires after ten minutes.
- The HTTP layer must always use an indistinguishable response for unknown or inactive accounts; it must never reflect whether an email matches. Email delivery happens **only after transaction commit**.
- `redeem_challenge(token)` uses a transactional conditional `UPDATE … RETURNING` to consume a non-expired challenge once, then creates an eight-hour session with a different purpose-bound token digest.
- `revoke_session(token)` persists revocation; the owner verification endpoint checks token digest, owner activity, expiry, and revocation on every request.
- Audits record fixed event names without raw tokens.

## Before enabling HTTP auth

1. Implement POST-only challenge issuance and redemption, with explicit origin/CSRF controls and layered rate limits (account, IP and delivery abuse).
2. Choose/configure a transactional mail delivery provider; ensure callbacks or database transaction timing cannot send failed challenges.
3. Issue the `__Host-curricula_admin_session` cookie solely from the server BFF using `Secure; HttpOnly; Path=/; SameSite=Lax`, without a `Domain` attribute. Enforce logout/revocation.
4. Verify end-to-end against isolated staging PostgreSQL using the approved data-owned schema, including concurrent challenge consumption, email delivery failures, replay, logout and disabled account scenarios.
5. Require explicit authorization before enabling production secrets, owner bootstrap, deployment or schema migrations.

CI exercises internal functions and PostgreSQL 16; it does **not** prove an operational login flow. The workflow pins the merged owner schema at `curricula-live/data@cd31abe0eefa296b52be33832de21dfb8273ab20`.
