# Semantic admission readout — development-only

Companion to the new semantic-admission data branch stacked on
`curricula-live/data` PR #27. This is a **read-only**, guarded view of
individually evidence-backed new canonical statements, separate from the
much larger unreviewed source graph.

## Routes

- `GET /v2-preview/concepts/{uuid}/admissions/?limit=30&offset=0`
  returns newly admitted statements connected to the canonical concept,
  their original source assertion witnesses, original predicate,
  supporting external references, direct/incoming direction, editorial
  review level, and exact predicate semantic scope.
- `GET /v2-preview/predicate-semantic-policies/`
  lists the five explicitly scoped new relation types and their source
  semantic meanings.

Returns are explicitly **not independent expert reviews or formal proofs**.
No new `subtype_of`, class-membership, pedagogical prerequisite, transitive
closure or synonym inferences are generated from the admitted CSO topic
hierarchy.

## Security / failure modes

- Entirely disabled under `APP_ENV=production`, even if the preview
  setting is accidentally enabled.
- Requires `V2_READ_PREVIEW_ENABLED=1` in an authorized staging
  configuration.
- Parameterized SQL, bounded pagination, GET-only, no-store responses.
- Missing database tables produce 503, unknown concept UUID produces 404.
- Never falls back to the historical V1 graph or returns synthesized
  proof metadata.

## Database integration

The endpoints read `knowledge.statement_admission` and
`knowledge.predicate_semantic_policy`, installed by the data-owned
`database/migrations/0005_knowledge_statement_admission.sql`.
Both tables are atomically synchronized with the canonical statements by
the data repository publisher.

Verified against **real PostgreSQL** and the full Django request stack
with the Artificial Intelligence concept: 6 direct admitted relations
returned, all proof/inference flags false; five predicate policies
returned.
