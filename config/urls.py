"""URL configuration for the curricula.live API."""

from django.contrib import admin
from django.urls import include, path

from core.views import api_root, health

urlpatterns = [
    path("", api_root, name="api-root"),
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("v1/", include("core.urls")),
]
