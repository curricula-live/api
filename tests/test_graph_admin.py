import uuid

import pytest
from django.contrib import admin
from django.urls import reverse

from core.admin import ConceptAdmin, RelationAdmin, RelationTypeAdmin
from core.models import Concept, Relation, RelationType


@pytest.mark.django_db
def test_graph_models_are_registered_with_admin():
    assert isinstance(admin.site._registry[Concept], ConceptAdmin)
    assert isinstance(admin.site._registry[RelationType], RelationTypeAdmin)
    assert isinstance(admin.site._registry[Relation], RelationAdmin)


def test_relation_admin_supports_graph_discovery_and_editing():
    relation_admin = admin.site._registry[Relation]

    assert relation_admin.list_display == ("source", "type", "target")
    assert relation_admin.list_filter == ("type",)
    assert relation_admin.search_fields == (
        "source__slug",
        "target__slug",
        "type__slug",
    )
    assert relation_admin.autocomplete_fields == ("source", "type", "target")


@pytest.mark.parametrize(
    ("model", "new_object", "primary_key"),
    [
        (Concept, Concept(slug="new-concept"), "slug"),
        (RelationType, RelationType(slug="new-type"), "slug"),
        (Relation, Relation(id=uuid.uuid4()), "id"),
    ],
)
def test_graph_admin_primary_keys_are_editable_only_when_creating(
    rf, model, new_object, primary_key
):
    model_admin = admin.site._registry[model]
    request = rf.get("/admin/")

    assert model_admin.get_readonly_fields(request, obj=None) == ()
    assert model_admin.get_readonly_fields(request, obj=new_object) == (primary_key,)


@pytest.mark.django_db
def test_admin_index_requires_authentication(client):
    response = client.get(reverse("admin:index"))

    assert response.status_code == 302
    assert response.url.startswith(reverse("admin:login"))
