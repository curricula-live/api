from django.db.models import Q

from .models import Concept, Relation

DEFAULT_NODE_LIMIT = 250
MAX_NODE_LIMIT = 1000
MAX_EDGE_LIMIT = 2500


def clamp_limit(raw_limit):
    try:
        value = int(raw_limit or DEFAULT_NODE_LIMIT)
    except (TypeError, ValueError):
        value = DEFAULT_NODE_LIMIT
    return max(1, min(value, MAX_NODE_LIMIT))


def build_graph_payload(query="", relation_type="", limit=DEFAULT_NODE_LIMIT):
    """Return a bounded, JSON-ready graph payload.

    A text query returns matching concepts plus as many one-hop neighbours as fit
    inside the node limit. Without a query, the first concepts by slug are used.
    """

    limit = clamp_limit(limit)
    query = (query or "").strip()
    relation_type = (relation_type or "").strip()

    relations = Relation.objects.select_related("source", "target").order_by(
        "source__slug", "type", "target__slug"
    )
    if relation_type:
        relations = relations.filter(type=relation_type)

    if query:
        matches = list(
            Concept.objects.filter(
                Q(slug__icontains=query)
                | Q(label__icontains=query)
                | Q(description__icontains=query)
            ).order_by("slug")[:limit]
        )
        matched_ids = [concept.id for concept in matches]
        candidate_edges = list(
            relations.filter(
                Q(source_id__in=matched_ids) | Q(target_id__in=matched_ids)
            )[:MAX_EDGE_LIMIT]
        )

        nodes_by_id = {concept.id: concept for concept in matches}
        neighbour_ids = []
        for relation in candidate_edges:
            for concept_id in (relation.source_id, relation.target_id):
                if concept_id not in nodes_by_id and concept_id not in neighbour_ids:
                    neighbour_ids.append(concept_id)

        remaining = max(0, limit - len(nodes_by_id))
        neighbours = Concept.objects.filter(id__in=neighbour_ids).order_by("slug")[:remaining]
        for concept in neighbours:
            nodes_by_id[concept.id] = concept
        nodes = sorted(nodes_by_id.values(), key=lambda concept: concept.slug)
    else:
        nodes = list(Concept.objects.order_by("slug")[:limit])
        candidate_edges = list(
            relations.filter(
                source_id__in=[concept.id for concept in nodes],
                target_id__in=[concept.id for concept in nodes],
            )[:MAX_EDGE_LIMIT]
        )

    node_ids = {concept.id for concept in nodes}
    edges = [
        relation
        for relation in candidate_edges
        if relation.source_id in node_ids and relation.target_id in node_ids
    ]

    total_concepts = Concept.objects.count()
    total_relations = Relation.objects.count()
    return {
        "nodes": [
            {
                "id": str(concept.id),
                "slug": concept.slug,
                "label": concept.label,
                "title": concept.description or concept.slug,
                "metadata": concept.metadata,
            }
            for concept in nodes
        ],
        "edges": [
            {
                "id": str(relation.id),
                "from": str(relation.source_id),
                "to": str(relation.target_id),
                "type": relation.type,
                "label": relation.type,
                "arrows": "to",
            }
            for relation in edges
        ],
        "stats": {
            "shown_nodes": len(nodes),
            "shown_edges": len(edges),
            "total_nodes": total_concepts,
            "total_edges": total_relations,
            "truncated": len(nodes) < total_concepts or len(edges) < total_relations,
        },
        "filters": {
            "q": query,
            "type": relation_type,
            "limit": limit,
        },
    }
