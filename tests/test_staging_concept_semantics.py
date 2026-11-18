"""Source topic edges must retain their direction and stay out of subtype proofs."""
from core.staging_concepts import text
from core.concept_documentation import _derive_subtypes

def test_broader_topic_target_is_broader():
    assert text("Integer addition", "source_broader_topic", "Arithmetic operation") == (
        "Integer addition has the recorded broader source topic Arithmetic operation."
    )

def test_source_topic_chain_does_not_become_subtype_proof():
    edges = [
        {"id": "source-a", "source": "integer-addition", "predicate": "source_broader_topic", "target": "arithmetic-operation"},
        {"id": "source-b", "source": "arithmetic-operation", "predicate": "source_broader_topic", "target": "computational-operation"},
    ]
    assert _derive_subtypes("integer-addition", edges, 2) == []
