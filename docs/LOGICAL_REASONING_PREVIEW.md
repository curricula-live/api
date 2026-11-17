# Concept-page logical reasoning preview

`core.formal_propositional_proofs` checks symbolic natural-deduction certificates and tracks exact open assumptions. Rules now include OR elimination using two matching implications, NOT introduction by discharging an assumption leading to bottom, NOT elimination from an exact proposition/negation pair, and bottom elimination. Existing AND, implication and IFF rules remain.

`core.logical_reasoning` builds six closed schematic proofs and independently truth-table checks them. Run `python -m core.logical_reasoning` to export the deterministic web artifact. `GET /v1/concepts/{slug}/logical-reasoning/` exposes the fixed checked preview for existing supported concepts only, with no mutation or arbitrary-proof input.

These are propositional schemas over arbitrary Boolean propositions, not source-attested scientific properties of a canonical concept. Closed proof validation does not promote legacy statements or source-topic relations into logical axioms. The API formal branch contains the same checker implementation; data PR #26 defines the matching experimental certificate grammar.

Verification: 65 targeted API/proof/documentation tests pass; 138 formal-branch tests pass. The data branch's full suite reports 140 passed and 18 skipped. Web CI also independently checks every displayed step against all Boolean assignments and verifies the exported certificate fingerprints.
