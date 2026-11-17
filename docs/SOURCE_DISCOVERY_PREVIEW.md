# Source discovery: read-only V2 development preview

This endpoint family consumes the separate `knowledge_source` staging schema
populated from the **curricula-live/data** source reconciliation review queue.
It does not mutate, override or auto-import canonical `knowledge` records.

## Routes

- `GET /v2-preview/source-search/?q=tcp&limit=10`: candidate topic labels,
  source-native identifiers, and possible **unreviewed** canonical ID matches.
- `GET /v2-preview/source-relations/?source_id=cso%403.5&source_uri=https%3A%2F%2Fcso.kmi.open.ac.uk%2Ftopics%2Ftcp&limit=10`:
  original source predicate, exact witness, directed endpoints and possible
  canonical UUID candidates.
- `GET /v2-preview/source-predicates/?source_id=cso%403.5`: native IRI,
  proposed semantic label, and explicitly unapproved inference status.

The only source IDs currently supported are `cso@3.5` and
`curricula-historical-v1@1.0.0`.

## Security and semantic guarantees

- Every route is **GET only**, bounded, parameterized and returns
  `Cache-Control: no-store`.
- Disabled by default; requires `V2_READ_PREVIEW_ENABLED=1` and
  `APP_ENV` other than `production`. The production check is unconditional.
- Missing review DB tables produce 503, not a legacy-data fallback.
- Every response contains
  `source_review_verified=false`,
  `canonical_identity_approved=false`,
  `inference_eligible=false`,
  `provisional=true`.
- Source assertions are **not** treated as class-subtype proofs, equivalence
  certificates, accepted canonical statements or teaching prerequisites.
  `superTopicOf`, `relatedEquivalent` and `owl:sameAs` remain distinct.

## Data provisioning

The API never downloads source exports at runtime. To test, apply
`data/database/migrations/0002_source_reconciliation_staging.sql` to an
isolated local PostgreSQL database and run
`data/scripts/stage_source_reconciliation.py apply
--confirm-staging STAGE-UNREVIEWED-SOURCES`.

This requires the data feature branch and the matching API branch.
No production Vercel or PostgreSQL configuration is changed.
