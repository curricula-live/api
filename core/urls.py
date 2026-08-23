from django.urls import path

from core.views import (
    concept_detail,
    concept_list,
    concept_neighborhood,
    concept_prerequisites,
    relation_detail,
    relation_list,
    relation_type_list,
)

urlpatterns = [
    path("concepts/", concept_list, name="concept-list"),
    path("concepts/<str:slug>/", concept_detail, name="concept-detail"),
    path(
        "concepts/<str:slug>/neighborhood/",
        concept_neighborhood,
        name="concept-neighborhood",
    ),
    path(
        "concepts/<str:slug>/prerequisites/",
        concept_prerequisites,
        name="concept-prerequisites",
    ),
    path("relations/", relation_list, name="relation-list"),
    path("relations/<uuid:relation_id>/", relation_detail, name="relation-detail"),
    path("relation-types/", relation_type_list, name="relation-type-list"),
]
