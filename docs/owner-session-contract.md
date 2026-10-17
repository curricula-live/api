# Owner session contract (pre-implementation)

This draft introduces **pure security primitives only**. No login endpoints,
identity tables, secrets, challenge issuance, cookie delivery, or authorization
middleware are enabled by this PR.

## Boundaries

1. [data#18](https://github.com/curricula-live/data/issues/18) owns PostgreSQL `admin` DDL for the singleton active owner, one-time passwordless challenge, hashed revocable session and audit.
2. [api#43](https://github.com/curricula-live/api/issues/43) owns atomic challenge consumption (POST only), expiry/rate-limiting, email delivery, session creation, role/activation checks on every owner request, audit and logout.
3. [admin#2](https://github.com/curricula-live/admin/issues/2) consumes the API via a server-side BFF, with a host-only Secure HttpOnly cookie. It cannot infer `owner` from browser data.

`issue_opaque_token()` generates high-entropy one-time material. Store only
`fingerprint_token(token, "challenge")` or `fingerprint_token(token, "session")`
in the DB. `token_matches()` is constant-time, but does not ensure one-use:
database atomicity is mandatory before real authentication.

The provisional owner session verify response expected by the admin BFF is
`GET /v1/admin/auth/session/`, with JSON:
```json
{
  "contract_version": "owner-session@1",
  "authenticated": true,
  "active": true,
  "role": "owner",
  "subject_id": "<server-verified owner UUID>",
  "expires_at": "<UTC expiry timestamp>"
}
```

`owner_session_attestation()` must only accept values loaded from authoritative
database rows after credential verification. A request-supplied UUID or role is
**never trusted**. Failure must return an explicit 401/403 without this payload.
The endpoint itself does **not exist yet**, and no data migration is triggered.
