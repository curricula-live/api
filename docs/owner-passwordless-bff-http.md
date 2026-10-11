# BFF-only passwordless HTTP contract (draft)

The endpoint implementation is layered on the separately reviewed
[data#20](https://github.com/curricula-live/data/pull/20) operational schema
and [api#49](https://github.com/curricula-live/api/pull/49) transactional
challenge/session service. It does **not** enable owner login by default.

## API routes

All three routes accept **POST only** and require
`X-Admin-BFF-Secret` supplied by the **server-side admin BFF**.
Browser requests, including requests with an `Origin` or
`Sec-Fetch-Site` header, are not accepted.

| Path | Body / header | Response |
|---|---|---|
| `/v1/admin/auth/request/` | JSON `{"email": "..."}` | Neutral 202 for known and unknown addresses |
| `/v1/admin/auth/redeem/` | JSON `{"challenge": "..."}` | 200 with opaque session token **to BFF only**, otherwise 401 |
| `/v1/admin/auth/logout/` | `Authorization: Bearer <token>` | Idempotent 204; 503 if database unavailable |

A GET never consumes the challenge. The mail message uses a
`/login/verify#challenge=...` fragment so the challenge is not sent to
the admin web server during a GET. The user must explicitly submit the
challenge through a BFF POST. Never store the session token in
localStorage, JS-readable cookies or a browser response.

Session verification remains `GET /v1/admin/auth/session/` and reads the
current owner/session state from the database every time.

## Explicit configuration required

All values are unset or false by default:

- `OWNER_AUTH_ENABLED=true` — turns on read-only session verification
  only when a reviewed owner database exists.
- `OWNER_AUTH_HTTP_ENABLED=true` — **separate** gate for these POST routes.
- `OWNER_BFF_SHARED_SECRET` — at least 32 characters, a genuine
  cryptographically random secret set in **both** trusted backends.
- `OWNER_LOGIN_LINK_BASE=https://admin.curricula.live/login/verify`
  — URL allowlisted by exact scheme, host and path (dev loopback optional).
- `OWNER_LOGIN_SENDER` — a configured email sender.
- Django `EMAIL_BACKEND` and SMTP credentials — configured separately
  in secret environment settings. Never put credentials in Git.

The email challenge and owner account are provisioned only by reviewed
operational tooling, never by public self-registration. The owner
email-address lookup and issuance cooldown run inside a database
transaction and return the same HTTP body for known/unknown addresses.

## Requirements before live activation

The BFF must enforce same-origin request validation, anti-CSRF protection,
proper `__Host-` Secure HttpOnly SameSite cookie issuance and clearing,
request throttling, and safe, no-store/Referrer-Policy responses. Validate
provider email delivery and lifecycle telemetry without token logging.
Configure stronger per-source rate limiting in a shared store or at the
edge. Integration/E2E tests must cover email scanners, browser back/forward
cache, replay, cookie scope, account deactivation and session revocation.

**This PR is a contract for code review, not authorization to enable the
feature in production or connect production email credentials.**
