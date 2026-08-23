from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from core.models import Concept, Relation, RelationType


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


def _relation_payload(relation):
    return {
        "id": str(relation.id),
        "source": relation.source_id,
        "type": relation.type_id,
        "target": relation.target_id,
    }


@require_GET
def relation_list(request):
    relations = Relation.objects.all()

    for parameter, field in (
        ("source", "source_id"),
        ("type", "type_id"),
        ("target", "target_id"),
    ):
        value = request.GET.get(parameter)
        if value is not None:
            relations = relations.filter(**{field: value})

    relations = relations.order_by("source_id", "type_id", "target_id", "id")
    return JsonResponse({"results": [_relation_payload(relation) for relation in relations]})


@require_GET
def relation_detail(request, relation_id):
    relation = get_object_or_404(Relation, id=relation_id)
    return JsonResponse(_relation_payload(relation))


@require_GET
def relation_type_list(request):
    relation_types = RelationType.objects.order_by("slug").values("slug")
    return JsonResponse({"results": list(relation_types)})
