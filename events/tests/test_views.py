import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from .factories import ApiKeyFactory, EventFactory


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def authed_client():
    client = APIClient()
    api_key = ApiKeyFactory()
    client.credentials(HTTP_AUTHORIZATION=f"Api-Key {api_key.key}")
    return client


@pytest.fixture
def admin_client_drf(django_user_model):
    user = django_user_model.objects.create_superuser(
        username="admin", password="adminpass", email="admin@test.com"
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class TestHealthView:
    def test_health_no_auth_required(self, api_client):
        response = api_client.get("/api/health/")
        assert response.status_code == 200
        assert response.data["api"] == "ok"

    @pytest.mark.django_db
    def test_health_includes_database(self, api_client):
        response = api_client.get("/api/health/")
        assert "database" in response.data


@pytest.mark.django_db
class TestIngestView:
    def test_ingest_accepted(self, authed_client):
        data = {"source": "github", "event_type": "push", "payload": {"ref": "main"}}
        response = authed_client.post("/api/ingest/", data, format="json")
        assert response.status_code == 202
        assert "id" in response.data

    def test_ingest_requires_auth(self, api_client):
        data = {"source": "github", "event_type": "push", "payload": {}}
        response = api_client.post("/api/ingest/", data, format="json")
        assert response.status_code in (401, 403)

    def test_ingest_invalid_payload(self, authed_client):
        response = authed_client.post("/api/ingest/", {}, format="json")
        assert response.status_code == 400

    def test_ingest_invalid_source(self, authed_client):
        data = {"source": "bad source!", "event_type": "push", "payload": {}}
        response = authed_client.post("/api/ingest/", data, format="json")
        assert response.status_code == 400


@pytest.mark.django_db
class TestEventListView:
    def test_list_events(self, authed_client):
        EventFactory.create_batch(3)
        response = authed_client.get("/api/events/")
        assert response.status_code == 200
        assert len(response.data["results"]) == 3

    def test_filter_by_source(self, authed_client):
        EventFactory(source="github")
        EventFactory(source="sentry")
        response = authed_client.get("/api/events/?source=github")
        assert response.status_code == 200
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["source"] == "github"

    def test_filter_by_category(self, authed_client):
        EventFactory(category="alert", classified=True)
        EventFactory(category="info", classified=True)
        response = authed_client.get("/api/events/?category=alert")
        assert len(response.data["results"]) == 1

    def test_filter_by_severity(self, authed_client):
        EventFactory(severity="critical")
        EventFactory(severity="low")
        response = authed_client.get("/api/events/?severity=critical")
        assert len(response.data["results"]) == 1

    def test_requires_auth(self, api_client):
        response = api_client.get("/api/events/")
        assert response.status_code in (401, 403)


@pytest.mark.django_db
class TestEventDetailView:
    def test_get_event(self, authed_client):
        event = EventFactory()
        response = authed_client.get(f"/api/events/{event.pk}/")
        assert response.status_code == 200
        assert response.data["id"] == str(event.pk)

    def test_nonexistent_event(self, authed_client):
        response = authed_client.get("/api/events/00000000-0000-0000-0000-000000000000/")
        assert response.status_code == 404


@pytest.mark.django_db
class TestEventSearchView:
    def test_empty_query_returns_empty(self, authed_client):
        EventFactory()
        response = authed_client.get("/api/events/search/")
        assert response.status_code == 200
        assert len(response.data["results"]) == 0

    def test_requires_auth(self, api_client):
        response = api_client.get("/api/events/search/?q=test")
        assert response.status_code in (401, 403)


@pytest.mark.django_db
class TestApiKeyListCreateView:
    def test_list_keys_admin(self, admin_client_drf):
        ApiKeyFactory.create_batch(2)
        response = admin_client_drf.get("/api/keys/")
        assert response.status_code == 200
        assert len(response.data) == 2

    def test_create_key_admin(self, admin_client_drf):
        response = admin_client_drf.post("/api/keys/", {"name": "new-key"}, format="json")
        assert response.status_code == 201
        assert response.data["name"] == "new-key"
        assert len(response.data["key"]) == 64

    def test_non_admin_forbidden(self, authed_client):
        response = authed_client.get("/api/keys/")
        assert response.status_code == 403


@pytest.mark.django_db
class TestApiKeyDetailView:
    def test_patch_key(self, admin_client_drf):
        key = ApiKeyFactory()
        response = admin_client_drf.patch(
            f"/api/keys/{key.pk}/", {"is_active": False}, format="json"
        )
        assert response.status_code == 200
        assert response.data["is_active"] is False

    def test_delete_key(self, admin_client_drf):
        key = ApiKeyFactory()
        response = admin_client_drf.delete(f"/api/keys/{key.pk}/")
        assert response.status_code == 204

    def test_nonexistent_key(self, admin_client_drf):
        response = admin_client_drf.patch("/api/keys/99999/", {"name": "x"}, format="json")
        assert response.status_code == 404
