"""URL configuration for the curricula.live API."""

from core.owner_mail_cron import dispatch_owner_mail_cron, maintain_owner_mail_cron
from django.contrib import admin
from django.urls import include, path

from core.views import api_root, health
from core.staging_db_diagnostic import staging_database_health
from core.atlas_preview import atlas_preview
from core.atlas_neighborhood import concept_relationships_preview
from core.public_v2 import concepts as public_concepts, concept_detail as public_concept_detail, concept_statements
from core.v2_preview import concept_by_id_preview, concept_by_slug_preview, concept_list_preview

urlpatterns = [
    path("internal/cron/owner-mail/dispatch/", dispatch_owner_mail_cron),
    path("internal/cron/owner-mail/maintain/", maintain_owner_mail_cron),
    path("", api_root, name="api-root"),
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("internal/staging-db-health/", staging_database_health, name="staging-db-health"),
    path("v1/", include("core.urls")),
    path("v2/concepts/", public_concepts, name="v2-concepts"),
    path("v2/concepts/<uuid:concept_id>/", public_concept_detail, name="v2-concept-detail"),
    path("v2/concepts/<uuid:concept_id>/statements/", concept_statements, name="v2-concept-statements"),
    path("v2-preview/atlas/", atlas_preview, name="v2-preview-atlas"),
    path("v2-preview/concepts/", concept_list_preview, name="v2-preview-concept-list"),
    path("v2-preview/concepts/<uuid:concept_id>/relationships/", concept_relationships_preview, name="v2-preview-concept-relationships"),
    path("v2-preview/concepts/by-slug/<slug:slug>/", concept_by_slug_preview, name="v2-preview-concept-slug"),
    path("v2-preview/concepts/<uuid:concept_id>/", concept_by_id_preview, name="v2-preview-concept-uuid"),
]
