from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from core.models import Concept


def health(request):
    return JsonResponse(
        {
            "status": "ok",
            "service": "curricula.live api",
        }
    )


def concept_list(request):
    concepts = Concept.objects.order_by("slug").values("slug")
    return JsonResponse({"results": list(concepts)})


def concept_detail(request, slug):
    concept = get_object_or_404(Concept, slug=slug)
    return JsonResponse({"slug": concept.slug})
