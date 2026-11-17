import pytest
from core.models import Concept

pytestmark = pytest.mark.django_db


def test_logical_schema_endpoint_is_read_only_and_scoped(client):
    Concept.objects.create(slug='boolean')
    response = client.get('/v1/concepts/boolean/logical-reasoning/')
    assert response.status_code == 200
    assert response['Cache-Control'] == 'no-store'
    data = response.json()
    assert len(data['examples']) == 6
    assert data['canonical_knowledge_changed'] is False
    assert all(e['verification']['logical_rules_checked'] for e in data['examples'])
    assert client.post('/v1/concepts/boolean/logical-reasoning/').status_code == 405


def test_no_schema_or_concept_is_invented(client):
    Concept.objects.create(slug='unrelated')
    assert client.get('/v1/concepts/unrelated/logical-reasoning/').status_code == 404
    assert client.get('/v1/concepts/missing/logical-reasoning/').status_code == 404


def test_operator_page_only_receives_relevant_examples(client):
    Concept.objects.create(slug='not')
    data = client.get('/v1/concepts/not/logical-reasoning/').json()
    assert {e['id'] for e in data['examples']} == {'modus-tollens', 'de-morgan'}
