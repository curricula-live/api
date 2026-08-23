from django.urls import path

from core.views import concept_detail, concept_list

urlpatterns = [
    path("concepts/", concept_list, name="concept-list"),
    path("concepts/<str:slug>/", concept_detail, name="concept-detail"),
]
