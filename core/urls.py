from django.urls import path

from core.views import concept_detail, concept_list, relation_detail, relation_list

urlpatterns = [
    path("concepts/", concept_list, name="concept-list"),
    path("concepts/<str:slug>/", concept_detail, name="concept-detail"),
    path("relations/", relation_list, name="relation-list"),
    path("relations/<uuid:relation_id>/", relation_detail, name="relation-detail"),
]
