from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from .models import Concept, Relation
from .serializers import ConceptSerializer, RelationSerializer

class ConceptViewSet(ModelViewSet):
    queryset = Concept.objects.all()
    serializer_class = ConceptSerializer
    search_fields = ["slug", "label", "description"]
    ordering_fields = ["slug", "label", "updated_at"]

class RelationViewSet(ModelViewSet):
    queryset = Relation.objects.select_related("source", "target").all()
    serializer_class = RelationSerializer
    filterset_fields = ["type", "source", "target"]

@api_view(["GET"])
@permission_classes([AllowAny])
def graph_data(request):
    concepts = Concept.objects.all()
    relations = Relation.objects.select_related("source", "target").all()
    return Response({
        "nodes": [{"id": c.id, "slug": c.slug, "label": c.label, "metadata": c.metadata} for c in concepts],
        "edges": [{"id": r.id, "from": r.source_id, "to": r.target_id, "type": r.type, "label": r.type} for r in relations],
    })
