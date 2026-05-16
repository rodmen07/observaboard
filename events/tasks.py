import json
import logging
import os

from django.contrib.postgres.search import SearchVector

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Classification rules
# Deterministic, no external API needed — demonstrates Celery + async patterns.
# ---------------------------------------------------------------------------

_CATEGORY_RULES = [
    ("deployment", ["deploy", "release", "rollout", "push", "publish", "build", "ci", "cd", "pipeline"]),
    ("security",   ["auth", "login", "logout", "password", "token", "key", "secret", "breach", "vuln", "cve", "firewall", "iam", "permission"]),
    ("alert",      ["alert", "alarm", "error", "exception", "fail", "crash", "timeout", "down", "outage", "incident", "pager"]),
    ("metric",     ["metric", "latency", "throughput", "rps", "cpu", "memory", "disk", "request", "response", "p99", "p95", "slo"]),
]


def _classify(source: str, event_type: str, payload: dict) -> tuple[str, str, str]:
    """Return (category, severity, summary)."""
    corpus = " ".join([
        source.lower(),
        event_type.lower(),
        json.dumps(payload).lower(),
    ])

    category = "info"
    for cat, keywords in _CATEGORY_RULES:
        if any(kw in corpus for kw in keywords):
            category = cat
            break

    # Severity heuristics
    severity = "low"
    if any(w in corpus for w in ["critical", "outage", "breach", "crash", "down"]):
        severity = "critical"
    elif any(w in corpus for w in ["error", "fail", "exception", "alert", "incident"]):
        severity = "high"
    elif any(w in corpus for w in ["warn", "degraded", "slow", "timeout"]):
        severity = "medium"

    action = event_type.replace("_", " ").replace(".", " ").title()
    summary = f"[{source}] {action}"
    if payload.get("message"):
        summary += f": {str(payload['message'])[:200]}"
    elif payload.get("description"):
        summary += f": {str(payload['description'])[:200]}"

    return category, severity, summary


def classify_event(event_id: str) -> None:
    """
    Classify an ingested event and update its search vector.
    Runs synchronously in the request cycle (classification is pure Python).
    """
    from .models import Event

    logger.info("Classifying event %s", event_id)

    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        logger.warning("Event %s not found, skipping classification", event_id)
        return

    try:
        category, severity, summary = _classify(
            event.source, event.event_type, event.raw_payload
        )

        Event.objects.filter(id=event_id).update(
            classified=True,
            category=category,
            severity=severity,
            summary=summary,
            search_vector=(
                SearchVector("source", weight="A")
                + SearchVector("event_type", weight="A")
                + SearchVector("summary", weight="B")
            ),
        )
        logger.info("Classified event %s as %s/%s", event_id, category, severity)
    except Exception:
        logger.exception("Failed to classify event %s", event_id)
        raise


def enqueue_classify_task(event_id: str) -> None:
    """
    Enqueue a Cloud Tasks HTTP task to classify the event asynchronously.

    When CLOUD_TASKS_QUEUE is not set (local dev / CI), falls back to a direct
    synchronous call so no GCP credentials are required.
    """
    queue_name = os.environ.get("CLOUD_TASKS_QUEUE", "")
    if not queue_name:
        classify_event(event_id)
        return

    project = os.environ.get("GCP_PROJECT_ID", "")
    location = os.environ.get("GCP_REGION", "us-central1")
    service_url = os.environ.get("CLOUD_RUN_SERVICE_URL", "").rstrip("/")
    sa_email = os.environ.get("CLOUD_TASKS_SA_EMAIL", "")

    try:
        from google.cloud import tasks_v2
        from google.protobuf import duration_pb2

        client = tasks_v2.CloudTasksClient()
        parent = client.queue_path(project, location, queue_name)

        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": f"{service_url}/api/tasks/classify/",
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"event_id": event_id}).encode(),
                "oidc_token": {
                    "service_account_email": sa_email,
                    "audience": service_url,
                },
            },
            "dispatch_deadline": duration_pb2.Duration(seconds=30),
        }

        client.create_task(request={"parent": parent, "task": task})
        logger.info("Enqueued classify task for event %s", event_id)
    except Exception:
        logger.exception("Failed to enqueue classify task for event %s; classifying inline", event_id)
        classify_event(event_id)
