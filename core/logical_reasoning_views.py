"""Read-only, checked logical schemas, separate from canonical graph claims."""
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET
from core.models import Concept
from core.logical_reasoning import logical_reasoning_for_concept


@require_GET
def concept_logical_reasoning(request, slug):
    get_object_or_404(Concept, slug=slug)
    bundle = logical_reasoning_for_concept(slug)
    if bundle is None:
        raise Http404("No logical schema preview for this concept")
    return JsonResponse(bundle, headers={"Cache-Control": "no-store"})
