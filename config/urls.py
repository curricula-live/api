"""URL configuration for the curricula.live API."""

from django.contrib import admin
from django.urls import path

from core.views import concept_detail, concept_list, health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("api/concepts/", concept_list, name="concept-list"),
    path("api/concepts/<str:slug>/", concept_detail, name="concept-detail"),
]
