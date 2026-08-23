from collections import deque

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from core.models import Concept, Relation, RelationType


PREREQUISITE_RELATION_TYPE = "prerequisite_of"
DEFAULT_MAX_DEPTH = 3
DEFAULT_MAX_NODES = 100
MAX_DEPTH = 10
MAX_NODES = 500


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


@require_GET
def concept_neighborhood(request, slug):
    concept = get_object_or_404(Concept, slug=slug)
    ordering = ("source_id", "type_id", "target_id", "id")
    outgoing = Relation.objects.filter(source=concept).order_by(*ordering)
    incoming = Relation.objects.filter(target=concept).order_by(*ordering)

    return JsonResponse(
        {
            "concept": {"slug": concept.slug},
            "outgoing": [_relation_payload(relation) for relation in outgoing],
            "incoming": [_relation_payload(relation) for relation in incoming],
        }
    )


def _bounded_query_parameter(request, name, default, maximum):
    raw_value = request.GET.get(name)
    if raw_value is None:
        return default, None

    try:
        value = int(raw_value)
    except ValueError:
        return None, f"{name} must be an integer"

    if value < 0 or value > maximum:
        return None, f"{name} must be between 0 and {maximum}"

    return value, None


def _prerequisite_query(target_slug, visited=None):
    query = Relation.objects.filter(
        target_id=target_slug,
        type_id=PREREQUISITE_RELATION_TYPE,
    )
    if visited:
        query = query.exclude(source_id__in=visited)
    return query.order_by("source_id").values_list("source_id", flat=True)


@require_GET
def concept_prerequisites(request, slug):
    concept = get_object_or_404(Concept, slug=slug)

    max_depth, error = _bounded_query_parameter(
        request, "max_depth", DEFAULT_MAX_DEPTH, MAX_DEPTH
    )
    if error:
        return JsonResponse({"error": error}, status=400)

    max_nodes, error = _bounded_query_parameter(
        request, "max_nodes", DEFAULT_MAX_NODES, MAX_NODES
    )
    if error:
        return JsonResponse({"error": error}, status=400)

    if max_depth == 0:
        return JsonResponse(
            {
                "concept": {"slug": concept.slug},
                "relation_type": PREREQUISITE_RELATION_TYPE,
                "max_depth": max_depth,
                "max_nodes": max_nodes,
                "truncated": False,
                "results": [],
            }
        )

    if max_nodes == 0:
        truncated = _prerequisite_query(concept.slug, {concept.slug}).exists()
        return JsonResponse(
            {
                "concept": {"slug": concept.slug},
                "relation_type": PREREQUISITE_RELATION_TYPE,
                "max_depth": max_depth,
                "max_nodes": max_nodes,
                "truncated": truncated,
                "results": [],
            }
        )

    visited = {concept.slug}
    queue = deque([(concept.slug, 0)])
    results = []
    truncated = False

    while queue:
        current_slug, depth = queue.popleft()
        if depth >= max_depth:
            continue

        remaining = max_nodes - len(results)
        # Cycle-filter in SQL, then fetch only the remaining capacity plus a sentinel.
        prerequisite_slugs = _prerequisite_query(current_slug, visited)[: remaining + 1]

        for prerequisite_slug in prerequisite_slugs:
            if len(results) >= max_nodes:
                truncated = True
                queue.clear()
                break

            prerequisite_depth = depth + 1
            visited.add(prerequisite_slug)
            results.append({"slug": prerequisite_slug, "depth": prerequisite_depth})
            queue.append((prerequisite_slug, prerequisite_depth))

    return JsonResponse(
        {
            "concept": {"slug": concept.slug},
            "relation_type": PREREQUISITE_RELATION_TYPE,
            "max_depth": max_depth,
            "max_nodes": max_nodes,
            "truncated": truncated,
            "results": results,
        }
    )
