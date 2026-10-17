import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from core.models import ScholarlyRelease
from core.scholarly_contract import encode, public_export


@pytest.fixture
def artifact(tmp_path):
    bundle = {'schema_version': 1, 'source': {'id': 'acm-ccs', 'version': 'synthetic-test',
        'publisher': 'Synthetic test publisher', 'url': 'https://example.invalid/source', 'retrieved_on': '2026-10-15',
        'license': 'synthetic-test-only', 'publication_scope': 'public', 'sha256': 'a' * 64, 'distribution': 'official',
        'permission': {'reviewer': 'Test', 'date': '2026-10-15', 'evidence_url': 'https://example.invalid/permission',
                       'scope': 'public-commercial-redistribution'}},
        'source_review': {'status': 'approved', 'reviewer': 'Test', 'date': '2026-10-15', 'rationale': 'Synthetic fixture'},
        'completeness': 'partial', 'nodes': [
            {'id': 'root', 'label': 'Synthetic root', 'kind': 'classification', 'parents': [], 'locator': '#root'},
            {'id': 'child', 'label': 'Synthetic child', 'kind': 'classification', 'parents': ['root'], 'locator': '#child'}],
        'mappings': [], 'definitions': []}
    path = tmp_path / 'public.json'
    path.write_bytes(encode(public_export(bundle)))
    return path


@pytest.mark.django_db
def test_installer_plan_idempotency_and_immutable_versions(artifact, settings):
    settings.APP_ENV = 'development'
    call_command('install_scholarly_release', str(artifact))
    assert ScholarlyRelease.objects.count() == 0
    call_command('install_scholarly_release', str(artifact), apply=True)
    call_command('install_scholarly_release', str(artifact), apply=True)
    assert ScholarlyRelease.objects.count() == 1
    altered = json.loads(artifact.read_text())
    altered['nodes'][0]['label'] = 'Different'
    artifact.write_bytes(encode(public_export(altered)))
    with pytest.raises(CommandError, match='immutable'):
        call_command('install_scholarly_release', str(artifact), apply=True)
    settings.APP_ENV = 'production'
    with pytest.raises(CommandError, match='restricted'):
        call_command('install_scholarly_release', str(artifact), apply=True)


@pytest.mark.django_db
def test_publication_rejected_without_rights_or_with_drafts(artifact, settings):
    settings.APP_ENV = 'development'
    payload = json.loads(artifact.read_text())
    payload['source']['publication_scope'] = 'restricted'
    artifact.write_bytes(encode(payload))
    with pytest.raises(CommandError, match='not permitted'):
        call_command('install_scholarly_release', str(artifact), apply=True)
    assert not ScholarlyRelease.objects.exists()


@pytest.mark.django_db
def test_api_hierarchy_bounds_and_evidence(artifact, settings, client):
    settings.APP_ENV = 'development'
    call_command('install_scholarly_release', str(artifact), apply=True)
    base = '/v1/scholarly/sources/acm-ccs/synthetic-test/nodes/'
    assert client.get('/v1/scholarly/sources/').json()['results'][0]['version'] == 'synthetic-test'
    root = client.get(base).json()['results']
    assert [n['id'] for n in root] == ['root']
    assert root[0]['mapping_status'] == 'no_published_mapping'
    assert [n['id'] for n in client.get(base, {'parent': 'root'}).json()['results']] == ['child']
    assert client.get(base, {'node': 'child'}).json()['results'][0]['parents'] == ['root']
    for query in ({'limit': 101}, {'offset': -1}, {'limit': 'x'}):
        assert client.get(base, query).status_code == 400
    assert client.get('/v1/scholarly/sources/acm-ccs/missing/nodes/').status_code == 404
    assert client.post(base).status_code == 405
    assert client.get('/v1/concepts/queue/evidence/').json()['results'] == []
