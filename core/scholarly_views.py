"""Bounded, version-addressed public projections. Candidate content is never exposed."""
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from core.models import ScholarlyRelease


def page(request, rows):
    try:
        limit = int(request.GET.get('limit', '50'))
        offset = int(request.GET.get('offset', '0'))
        if not 1 <= limit <= 100 or not 0 <= offset <= 100000:
            raise ValueError
    except ValueError:
        return JsonResponse({'error': 'limit must be 1..100; offset must be 0..100000'}, status=400)
    return JsonResponse({'count': len(rows), 'limit': limit, 'offset': offset,
                         'next_offset': offset + limit if offset + limit < len(rows) else None,
                         'results': rows[offset:offset + limit]})


@require_GET
def sources(request):
    rows = [{'source_id': r.source_id, 'version': r.version, 'artifact_sha256': r.sha256,
             'source': r.payload['source'], 'completeness': r.payload['completeness']}
            for r in ScholarlyRelease.objects.order_by('source_id', 'version').iterator()]
    return page(request, rows)


@require_GET
def nodes(request, source_id, version):
    release = get_object_or_404(ScholarlyRelease, source_id=source_id, version=version)
    payload = release.payload
    parent = request.GET.get('parent', '')
    rows = [n for n in payload['nodes'] if (parent in n['parents'] if parent else not n['parents'])]
    node_id = request.GET.get('node')
    if node_id is not None:
        rows = [n for n in payload['nodes'] if n['id'] == node_id]
    # Fields are explicitly allowlisted by the installer. Unknown state is explicit.
    approved = payload['mappings']
    rows = [{**n, 'mapping_status': 'reviewed' if any(m['node_id'] == n['id'] for m in approved)
             else 'no_published_mapping', 'mappings': [m for m in approved if m['node_id'] == n['id']],
             'source': payload['source']} for n in rows]
    return page(request, rows)


@require_GET
def concept_evidence(request, slug):
    # Published evidence only. Absence does not imply no private candidates exist.
    rows = []
    for release in ScholarlyRelease.objects.order_by('source_id', 'version').iterator():
        p = release.payload
        for kind, key in (('mapping', 'mappings'), ('definition', 'definitions')):
            for item in p[key]:
                if item['canonical_slug'] == slug:
                    rows.append({'kind': kind, 'source': p['source'], 'evidence': item})
    return page(request, rows)
