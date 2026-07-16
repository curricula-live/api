from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import Concept, Relation
from .serializers import ConceptSerializer, RelationSerializer
from .services import build_graph_payload


class ConceptViewSet(ModelViewSet):
    queryset = Concept.objects.all()
    serializer_class = ConceptSerializer
    search_fields = ["slug", "label", "description"]
    ordering_fields = ["slug", "label", "updated_at"]
    ordering = ["slug"]


class RelationViewSet(ModelViewSet):
    queryset = Relation.objects.select_related("source", "target").all()
    serializer_class = RelationSerializer
    filterset_fields = ["type", "source", "target"]
    search_fields = ["type", "source__slug", "target__slug"]
    ordering_fields = ["type", "source__slug", "target__slug", "updated_at"]


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok", "service": "curricula.live api"})


@api_view(["GET"])
@permission_classes([AllowAny])
def graph_data(request):
    return Response(
        build_graph_payload(
            query=request.query_params.get("q", ""),
            relation_type=request.query_params.get("type", ""),
            limit=request.query_params.get("limit"),
        )
    )
