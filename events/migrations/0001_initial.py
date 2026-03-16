import uuid
import django.contrib.postgres.indexes
import django.contrib.postgres.search
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ApiKey",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("key", models.CharField(editable=False, max_length=64, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Event",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("source", models.CharField(db_index=True, max_length=120)),
                ("event_type", models.CharField(db_index=True, max_length=120)),
                ("raw_payload", models.JSONField()),
                ("classified", models.BooleanField(default=False)),
                ("category", models.CharField(
                    blank=True,
                    choices=[
                        ("deployment", "Deployment"),
                        ("security", "Security"),
                        ("alert", "Alert"),
                        ("metric", "Metric"),
                        ("info", "Info"),
                    ],
                    max_length=20,
                )),
                ("severity", models.CharField(
                    choices=[
                        ("low", "Low"),
                        ("medium", "Medium"),
                        ("high", "High"),
                        ("critical", "Critical"),
                    ],
                    default="low",
                    max_length=10,
                )),
                ("summary", models.TextField(blank=True)),
                ("search_vector", django.contrib.postgres.search.SearchVectorField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="event",
            index=django.contrib.postgres.indexes.GinIndex(fields=["search_vector"], name="events_even_search__gin"),
        ),
    ]
