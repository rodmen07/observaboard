import secrets
import uuid

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models


class ApiKey(models.Model):
    key = models.CharField(max_length=64, unique=True, editable=False)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({'active' if self.is_active else 'revoked'})"

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = secrets.token_hex(32)
        super().save(*args, **kwargs)


class Event(models.Model):
    CATEGORY_CHOICES = [
        ("deployment", "Deployment"),
        ("security", "Security"),
        ("alert", "Alert"),
        ("metric", "Metric"),
        ("info", "Info"),
    ]
    SEVERITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.CharField(max_length=120, db_index=True)
    event_type = models.CharField(max_length=120, db_index=True)
    raw_payload = models.JSONField()

    # Set by Celery classification task
    classified = models.BooleanField(default=False)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, blank=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default="low")
    summary = models.TextField(blank=True)

    # PostgreSQL full-text search vector (updated by trigger/signal)
    search_vector = SearchVectorField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [GinIndex(fields=["search_vector"])]

    def __str__(self):
        return f"[{self.source}] {self.event_type} — {self.id}"
