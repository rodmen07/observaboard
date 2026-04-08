import pytest
from rest_framework.exceptions import ValidationError
from events.serializers import EventSerializer, IngestSerializer, ApiKeySerializer
from .factories import EventFactory, ApiKeyFactory


@pytest.mark.django_db
class TestEventSerializer:
    def test_read_only_fields(self):
        event = EventFactory(source="test-src", event_type="test.event")
        data = EventSerializer(event).data
        assert data["source"] == "test-src"
        assert data["event_type"] == "test.event"
        assert "id" in data
        assert "created_at" in data

    def test_all_fields_present(self):
        event = EventFactory()
        data = EventSerializer(event).data
        expected_fields = {
            "id", "source", "event_type", "raw_payload",
            "classified", "category", "severity", "summary",
            "created_at", "updated_at",
        }
        assert set(data.keys()) == expected_fields


class TestIngestSerializer:
    def test_valid_input(self):
        data = {"source": "github", "event_type": "push", "payload": {"ref": "main"}}
        s = IngestSerializer(data=data)
        assert s.is_valid()

    def test_invalid_source_chars(self):
        data = {"source": "bad source!", "event_type": "push", "payload": {}}
        s = IngestSerializer(data=data)
        assert not s.is_valid()
        assert "source" in s.errors

    def test_valid_source_chars(self):
        data = {"source": "my-source_v2.0", "event_type": "push", "payload": {}}
        s = IngestSerializer(data=data)
        assert s.is_valid()

    def test_missing_required_fields(self):
        s = IngestSerializer(data={})
        assert not s.is_valid()
        assert "source" in s.errors
        assert "event_type" in s.errors
        assert "payload" in s.errors


@pytest.mark.django_db
class TestApiKeySerializer:
    def test_key_is_read_only(self):
        key = ApiKeyFactory()
        data = ApiKeySerializer(key).data
        assert "key" in data
        assert data["key"] == key.key

    def test_fields_present(self):
        key = ApiKeyFactory()
        data = ApiKeySerializer(key).data
        expected = {"id", "key", "name", "is_active", "created_at", "last_used_at"}
        assert set(data.keys()) == expected
