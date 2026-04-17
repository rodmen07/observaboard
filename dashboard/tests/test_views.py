import pytest
from django.test import Client

from events.tests.factories import ApiKeyFactory, EventFactory


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def staff_client(client, django_user_model):
    django_user_model.objects.create_user(
        username="staffuser", password="staffpass", is_staff=True
    )
    client.login(username="staffuser", password="staffpass")
    return client


@pytest.mark.django_db
class TestIndexView:
    def test_renders_without_login(self, client):
        response = client.get("/dashboard/")
        assert response.status_code == 200
        assert b"Dashboard" in response.content

    def test_renders_with_events(self, client):
        EventFactory.create_batch(3, category="alert", severity="high")
        response = client.get("/dashboard/")
        assert response.status_code == 200
        assert b"Dashboard" in response.content

    def test_renders_empty(self, client):
        response = client.get("/dashboard/")
        assert response.status_code == 200


@pytest.mark.django_db
class TestEventsListView:
    def test_renders_without_login(self, client):
        response = client.get("/dashboard/events/")
        assert response.status_code == 200

    def test_renders_events(self, client):
        EventFactory.create_batch(3)
        response = client.get("/dashboard/events/")
        assert response.status_code == 200
        assert b"Events" in response.content

    def test_filter_by_source(self, client):
        EventFactory(source="github")
        EventFactory(source="sentry")
        response = client.get("/dashboard/events/?source=github")
        assert response.status_code == 200

    def test_htmx_returns_partial(self, client):
        EventFactory.create_batch(2)
        response = client.get(
            "/dashboard/events/", HTTP_HX_REQUEST="true"
        )
        assert response.status_code == 200
        # Partial should not contain full base template
        assert b"<!DOCTYPE html>" not in response.content


@pytest.mark.django_db
class TestEventDetailView:
    def test_renders_event(self, client):
        event = EventFactory(source="github", raw_payload={"ref": "main"})
        response = client.get(f"/dashboard/events/{event.pk}/")
        assert response.status_code == 200
        assert b"github" in response.content

    def test_nonexistent_event(self, client):
        response = client.get(
            "/dashboard/events/00000000-0000-0000-0000-000000000000/"
        )
        assert response.status_code == 404


@pytest.mark.django_db
class TestKeysView:
    def test_requires_login(self, client):
        response = client.get("/dashboard/keys/")
        assert response.status_code == 302

    def test_requires_staff(self, client, django_user_model):
        django_user_model.objects.create_user(username="regular", password="pass")
        client.login(username="regular", password="pass")
        response = client.get("/dashboard/keys/")
        assert response.status_code == 403

    def test_staff_can_access(self, staff_client):
        response = staff_client.get("/dashboard/keys/")
        assert response.status_code == 200
        assert b"API Keys" in response.content

    def test_create_key(self, staff_client):
        response = staff_client.post("/dashboard/keys/create/", {"name": "test-key"})
        assert response.status_code == 200
        assert b"test-key" in response.content

    def test_toggle_key(self, staff_client):
        key = ApiKeyFactory()
        assert key.is_active is True
        response = staff_client.post(f"/dashboard/keys/{key.pk}/toggle/")
        assert response.status_code == 200
        key.refresh_from_db()
        assert key.is_active is False

    def test_delete_key(self, staff_client):
        key = ApiKeyFactory()
        response = staff_client.post(f"/dashboard/keys/{key.pk}/delete/")
        assert response.status_code == 200
