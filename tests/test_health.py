import pytest
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import connection
from django.urls import reverse

from graph.models import Concept, Relation
from graph.services import build_graph_payload


@pytest.fixture
def sample_graph(db):
    queue = Concept.objects.create(
        slug="queue",
        label="Queue",
        description="First-in, first-out collection.",
    )
    fifo = Concept.objects.create(slug="fifo", label="FIFO")
    stack = Concept.objects.create(slug="stack", label="Stack")
    Relation.objects.create(source=fifo, target=queue, type="part_of")
    Relation.objects.create(source=stack, target=queue, type="related_to")
    return queue, fifo, stack


@pytest.mark.django_db
def test_health_endpoint_returns_service_info(client):
    response = client.get(reverse("health"))

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "curricula.live api",
    }


@pytest.mark.django_db
def test_graph_endpoint_filters_to_matching_neighbourhood(client, sample_graph):
    response = client.get(reverse("graph-data"), {"q": "fifo", "limit": 10})

    assert response.status_code == 200
    payload = response.json()
    assert {node["slug"] for node in payload["nodes"]} == {"fifo", "queue"}
    assert [edge["type"] for edge in payload["edges"]] == ["part_of"]
    assert payload["filters"]["q"] == "fifo"


@pytest.mark.django_db
def test_graph_payload_clamps_requested_limit(sample_graph):
    payload = build_graph_payload(limit=100000)

    assert payload["filters"]["limit"] == 1000


@pytest.mark.django_db
def test_anonymous_api_writes_are_rejected(client):
    response = client.post(
        "/api/concepts/",
        {"slug": "tree", "label": "Tree", "metadata": {}},
        content_type="application/json",
    )

    assert response.status_code in {401, 403}
    assert not Concept.objects.filter(slug="tree").exists()


@pytest.mark.django_db
def test_authenticated_user_without_model_permission_cannot_write(
    client,
    django_user_model,
):
    user = django_user_model.objects.create_user(
        username="reader",
        password="unused",
    )
    client.force_login(user)

    response = client.post(
        "/api/concepts/",
        {"slug": "tree", "label": "Tree", "metadata": {}},
        content_type="application/json",
    )

    assert response.status_code == 403
    assert not Concept.objects.filter(slug="tree").exists()


@pytest.mark.django_db
def test_user_with_add_permission_can_create_concept(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="editor",
        password="unused",
    )
    user.user_permissions.add(Permission.objects.get(codename="add_concept"))
    client.force_login(user)

    response = client.post(
        "/api/concepts/",
        {
            "slug": "tree",
            "label": "Tree",
            "description": "",
            "metadata": {},
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    assert Concept.objects.filter(slug="tree").exists()


@pytest.mark.django_db
def test_relation_rejects_invalid_self_reference():
    concept = Concept.objects.create(slug="graph", label="Graph")
    relation = Relation(source=concept, target=concept, type="prerequisite_of")

    with pytest.raises(ValidationError):
        relation.full_clean()


@pytest.mark.django_db
def test_staff_user_cannot_access_sql_workbench(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="staff",
        password="unused",
        is_staff=True,
    )
    client.force_login(user)

    response = client.get(reverse("graph_admin:sql-workbench"))

    assert response.status_code == 403


@pytest.mark.django_db
def test_superuser_sql_write_dry_run_rolls_back(client, django_user_model):
    if connection.vendor != "postgresql":
        pytest.skip("The SQL workbench targets PostgreSQL.")

    concept = Concept.objects.create(slug="array", label="Array")
    user = django_user_model.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="unused",
    )
    client.force_login(user)

    response = client.post(
        reverse("graph_admin:sql-workbench"),
        {
            "sql": "update concept set label = 'Changed' where slug = 'array'",
            "allow_write": "on",
            "dry_run": "on",
            "confirmation": "APPLY",
        },
    )

    assert response.status_code == 200
    concept.refresh_from_db()
    assert concept.label == "Array"
    assert b"rolled back" in response.content


@pytest.mark.django_db
def test_graph_admin_uses_json_script(client, django_user_model, sample_graph):
    user = django_user_model.objects.create_user(
        username="viewer",
        password="unused",
        is_staff=True,
    )
    client.force_login(user)

    response = client.get(reverse("graph_admin:graph-view"))

    assert response.status_code == 200
    assert b'id="graph-nodes"' in response.content
    assert b"UUID(" not in response.content
