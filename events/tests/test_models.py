import pytest
from events.models import Event
from .factories import ApiKeyFactory, EventFactory


@pytest.mark.django_db
class TestEvent:
    def test_create_event(self):
        event = EventFactory()
        assert event.pk is not None
        assert event.classified is False
        assert event.severity == "low"

    def test_uuid_primary_key(self):
        event = EventFactory()
        assert len(str(event.pk)) == 36  # UUID format

    def test_str(self):
        event = EventFactory(source="github", event_type="push")
        assert "github" in str(event)
        assert "push" in str(event)

    def test_ordering(self):
        EventFactory()  # creates earlier event for ordering check
        e2 = EventFactory()
        events = list(Event.objects.all())
        # Most recent first
        assert events[0].pk == e2.pk

    def test_category_choices(self):
        categories = [c[0] for c in Event.CATEGORY_CHOICES]
        assert "deployment" in categories
        assert "security" in categories
        assert "alert" in categories
        assert "metric" in categories
        assert "info" in categories

    def test_severity_choices(self):
        severities = [s[0] for s in Event.SEVERITY_CHOICES]
        assert "low" in severities
        assert "medium" in severities
        assert "high" in severities
        assert "critical" in severities


@pytest.mark.django_db
class TestApiKey:
    def test_auto_key_generation(self):
        key = ApiKeyFactory()
        assert len(key.key) == 64

    def test_key_unique(self):
        k1 = ApiKeyFactory()
        k2 = ApiKeyFactory()
        assert k1.key != k2.key

    def test_default_active(self):
        key = ApiKeyFactory()
        assert key.is_active is True

    def test_str_active(self):
        key = ApiKeyFactory(name="my-key")
        assert "my-key" in str(key)
        assert "active" in str(key)

    def test_str_revoked(self):
        key = ApiKeyFactory(name="old-key", is_active=False)
        assert "revoked" in str(key)
