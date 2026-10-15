# Django owner session verification endpoint (draft)

\`GET /v1/admin/auth/session/\` is the server-side BFF verification contract.
This draft route is disabled by default (\`OWNER_AUTH_ENABLED=false\`) and
requires the data-owned \`admin\` schema in [data#20](https://github.com/curricula-live/data/pull/20).

When explicitly enabled in a reviewed staging environment:
- Accept one opaque \`Authorization: Bearer <token>\` value, hash with
  \`fingerprint_token(token, "session")\`, and look up only the digest.
- Join \`admin.owner_session\` and \`admin.owner_principal\` on every request.
- Return \`owner-session@1\` attestation only if role is \`owner\`, account active,
  session unrevoked and unexpired.
- Return generic 401 on invalid token and 503 on schema/database failures;
  no fallback to Django superusers, role headers, JSON body or public v1 graph.
- Respond with \`Cache-Control: private, no-store\` and \`Vary: Authorization\`.

**Important:** No magic-link email is sent or redeemed by this PR. No
authentication is possible until explicit owner bootstrap, atomic challenge
redemption, session issuance, secure BFF cookie and CSRF/rate-limit work are
implemented and reviewed. Do not enable in production based on unit tests.
