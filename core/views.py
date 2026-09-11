import re
from collections import deque

from django.db.models import Case, IntegerField, Q, Value, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from core.models import Concept, Relation, RelationType


PREREQUISITE_RELATION_TYPE = "prerequisite_of"
DEFAULT_MAX_DEPTH = 3
DEFAULT_MAX_NODES = 100
MAX_DEPTH = 10
MAX_NODES = 500
DEFAULT_SEARCH_LIMIT = 20
MAX_SEARCH_LIMIT = 100
SEARCH_CATEGORIES = {"all", "concepts", "connections"}


@require_GET
def api_root(request):
    return JsonResponse(
        {
            "service": "curricula.live API",
            "latest_version": "v1",
            "versions": {"v1": "/v1/"},
        }
    )


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


def _normalize_search_query(value):
    normalized = value.strip().lower().replace("'", "").replace("’", "")
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return normalized


def _search_variants(normalized_query):
    variants = (
        normalized_query,
        normalized_query.replace("-", "_"),
        normalized_query.replace("-", ""),
    )
    return tuple(dict.fromkeys(variant for variant in variants if variant))


def _search_limit(request):
    raw_limit = request.GET.get("limit")
    if raw_limit is None:
        return DEFAULT_SEARCH_LIMIT, None

    try:
        limit = int(raw_limit)
    except ValueError:
        return None, "limit must be an integer"

    if limit < 1 or limit > MAX_SEARCH_LIMIT:
        return None, f"limit must be between 1 and {MAX_SEARCH_LIMIT}"

    return limit, None


def _concept_search(variants, limit):
    match = Q()
    exact = Q()
    for variant in variants:
        match |= Q(slug__icontains=variant)
        exact |= Q(slug__iexact=variant)

    concepts = (
        Concept.objects.filter(match)
        .annotate(
            _exact_match=Case(
                When(exact, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by("_exact_match", "slug")[:limit]
    )
    return list(concepts.values("slug"))


def _connection_search(variants, limit):
    match = Q()
    exact = Q()
    for variant in variants:
        match |= (
            Q(source_id__icontains=variant)
            | Q(type_id__icontains=variant)
            | Q(target_id__icontains=variant)
        )
        exact |= (
            Q(source_id__iexact=variant)
            | Q(type_id__iexact=variant)
            | Q(target_id__iexact=variant)
        )

    relations = (
        Relation.objects.filter(match)
        .annotate(
            _exact_match=Case(
                When(exact, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by("_exact_match", "source_id", "type_id", "target_id", "id")[:limit]
    )
    return [_relation_payload(relation) for relation in relations]


@require_GET
def search(request):
    query = request.GET.get("q")
    if query is None or not query.strip():
        return JsonResponse({"error": "q is required"}, status=400)

    normalized_query = _normalize_search_query(query)
    if not normalized_query:
        return JsonResponse({"error": "q must contain searchable text"}, status=400)

    category = request.GET.get("category", "all")
    if category not in SEARCH_CATEGORIES:
        return JsonResponse(
            {"error": "category must be one of: all, concepts, connections"},
            status=400,
        )

    limit, error = _search_limit(request)
    if error:
        return JsonResponse({"error": error}, status=400)

    variants = _search_variants(normalized_query)
    results = {}

    if category in {"all", "concepts"}:
        results["concepts"] = _concept_search(variants, limit)

    if category in {"all", "connections"}:
        results["connections"] = _connection_search(variants, limit)

    return JsonResponse({"query": query.strip(), "results": results})


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
