from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from core.models import Concept


def health(request):
    return JsonResponse(
        {
            "status": "ok",
            "service": "curricula.live api",
        }
    )


@require_GET
def concept_list(request):
    concepts = Concept.objects.order_by("slug").values("slug")
    return JsonResponse({"results": list(concepts)})


@require_GET
def concept_detail(request, slug):
    concept = get_object_or_404(Concept, slug=slug)
    return JsonResponse({"slug": concept.slug})
