"""URL configuration for the curricula.live API."""

from django.contrib import admin
from django.urls import include, path

from core.views import api_root, health
from core.atlas_preview import atlas_preview
from core.atlas_neighborhood import concept_relationships_preview
from core.v2_preview import concept_by_id_preview, concept_by_slug_preview, concept_list_preview

urlpatterns = [
    path("", api_root, name="api-root"),
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("v1/", include("core.urls")),
    path("v2-preview/atlas/", atlas_preview, name="v2-preview-atlas"),
    path("v2-preview/concepts/", concept_list_preview, name="v2-preview-concept-list"),
    path("v2-preview/concepts/<uuid:concept_id>/relationships/", concept_relationships_preview, name="v2-preview-concept-relationships"),
    path("v2-preview/concepts/by-slug/<slug:slug>/", concept_by_slug_preview, name="v2-preview-concept-slug"),
    path("v2-preview/concepts/<uuid:concept_id>/", concept_by_id_preview, name="v2-preview-concept-uuid"),
]
