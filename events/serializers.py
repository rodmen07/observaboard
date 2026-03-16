from rest_framework import serializers
from .models import Event, ApiKey


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = [
            "id", "source", "event_type", "raw_payload",
            "classified", "category", "severity", "summary",
            "created_at", "updated_at",
        ]
        read_only_fields = fields


class IngestSerializer(serializers.Serializer):
    source = serializers.CharField(max_length=120)
    event_type = serializers.CharField(max_length=120)
    payload = serializers.JSONField()

    def validate_source(self, value):
        if not all(c.isalnum() or c in "-_." for c in value):
            raise serializers.ValidationError(
                "source may only contain alphanumeric characters, hyphens, underscores, or dots."
            )
        return value


class ApiKeySerializer(serializers.ModelSerializer):
    # Only expose the raw key on creation; afterwards it's masked.
    key = serializers.CharField(read_only=True)

    class Meta:
        model = ApiKey
        fields = ["id", "key", "name", "is_active", "created_at", "last_used_at"]
        read_only_fields = ["id", "key", "created_at", "last_used_at"]
