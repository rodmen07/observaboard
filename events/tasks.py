import json
import logging

from celery import shared_task
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


@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
)
def classify_event(self, event_id: str):
    """
    Classify an ingested event and update its search vector.
    Runs asynchronously via Celery after ingest.
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
    except Exception as exc:
        logger.exception("Failed to classify event %s", event_id)
        raise self.retry(exc=exc)
