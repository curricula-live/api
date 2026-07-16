from django.urls import include, path
from rest_framework.routers import DefaultRouter

from graph.admin import ConceptAdmin, GraphAdminSite, RelationAdmin
from graph.models import Concept, Relation
from graph.views import ConceptViewSet, RelationViewSet, graph_data, health

router = DefaultRouter()
router.register("concepts", ConceptViewSet)
router.register("relations", RelationViewSet)

graph_admin = GraphAdminSite(name="graph_admin")
graph_admin.register(Concept, ConceptAdmin)
graph_admin.register(Relation, RelationAdmin)

urlpatterns = [
    path("admin/", graph_admin.urls),
    path("api/", include(router.urls)),
    path("api/health/", health, name="health"),
    path("api/graph/", graph_data, name="graph-data"),
]
