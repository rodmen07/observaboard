import pytest

from events.tasks import _classify, classify_event
from .factories import EventFactory


class TestClassifyFunction:
    def test_deployment_category(self):
        cat, sev, summary = _classify("github", "deploy.success", {"message": "deployed v1.2"})
        assert cat == "deployment"

    def test_security_category(self):
        cat, sev, summary = _classify("okta", "login.failed", {"user": "admin"})
        assert cat == "security"

    def test_alert_category(self):
        cat, sev, summary = _classify("pagerduty", "incident.triggered", {"message": "error rate high"})
        assert cat == "alert"

    def test_metric_category(self):
        cat, sev, summary = _classify("datadog", "metric.threshold", {"cpu": 95})
        assert cat == "metric"

    def test_info_fallback(self):
        cat, sev, summary = _classify("custom", "note", {"text": "hello"})
        assert cat == "info"

    def test_critical_severity(self):
        cat, sev, summary = _classify("monitor", "outage.detected", {})
        assert sev == "critical"

    def test_high_severity(self):
        cat, sev, summary = _classify("sentry", "error.new", {"message": "NullPointer"})
        assert sev == "high"

    def test_medium_severity(self):
        cat, sev, summary = _classify("monitor", "timeout.warning", {})
        assert sev == "medium"

    def test_low_severity(self):
        cat, sev, summary = _classify("custom", "note", {"text": "hello"})
        assert sev == "low"

    def test_summary_includes_source(self):
        cat, sev, summary = _classify("github", "push", {})
        assert "[github]" in summary

    def test_summary_includes_message(self):
        cat, sev, summary = _classify("github", "push", {"message": "merged PR #42"})
        assert "merged PR #42" in summary

    def test_summary_includes_description(self):
        cat, sev, summary = _classify("jira", "issue.created", {"description": "Fix the bug"})
        assert "Fix the bug" in summary


@pytest.mark.django_db
class TestClassifyEventTask:
    def test_classifies_event(self):
        event = EventFactory(source="github", event_type="deploy.success")
        classify_event(str(event.pk))
        event.refresh_from_db()
        assert event.classified is True
        assert event.category == "deployment"

    def test_nonexistent_event(self):
        # Should not raise
        classify_event("00000000-0000-0000-0000-000000000000")

    def test_sets_severity(self):
        event = EventFactory(
            source="pagerduty",
            event_type="incident",
            raw_payload={"message": "critical outage"},
        )
        classify_event(str(event.pk))
        event.refresh_from_db()
        assert event.severity == "critical"
