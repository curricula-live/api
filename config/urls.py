from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from graph.views import ConceptViewSet, RelationViewSet, graph_data

router = DefaultRouter()
router.register("concepts", ConceptViewSet)
router.register("relations", RelationViewSet)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api/graph/", graph_data, name="graph-data"),
]
