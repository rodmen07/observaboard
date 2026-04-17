"""Seed the database with realistic demo data for the dashboard."""

import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from events.models import ApiKey, Event
from events.tasks import _classify

User = get_user_model()

# Realistic event scenarios
SCENARIOS = [
    # Deployments
    ("github", "deploy.success", {"message": "Deployed api-gateway v2.14.0 to production", "sha": "a1b2c3d", "environment": "production"}),
    ("github", "deploy.success", {"message": "Deployed auth-service v1.8.3 to staging", "sha": "e4f5g6h", "environment": "staging"}),
    ("github", "deploy.failed", {"message": "Deploy of payment-service v3.1.0 failed: health check timeout", "sha": "i7j8k9l", "environment": "production"}),
    ("github", "push", {"message": "Merged PR #142: Add rate limiting to /api/search", "ref": "refs/heads/main", "author": "alice"}),
    ("github", "push", {"message": "Merged PR #139: Migrate user table to new schema", "ref": "refs/heads/main", "author": "bob"}),
    ("github", "release.published", {"message": "Released v2.15.0 - Q1 feature rollup", "tag": "v2.15.0"}),
    ("gitlab", "pipeline.success", {"message": "CI pipeline passed for main branch", "pipeline_id": 48291, "duration_seconds": 342}),
    ("gitlab", "pipeline.failed", {"message": "CI pipeline failed: test_auth_flow timed out", "pipeline_id": 48305, "duration_seconds": 600}),
    ("circleci", "build.complete", {"message": "Build #1847 passed all 312 tests", "workflow": "main-deploy", "duration": "5m42s"}),
    ("argocd", "rollout.complete", {"message": "Rollout of frontend v4.2.0 completed across 3 clusters", "app": "frontend", "clusters": ["us-east", "eu-west", "ap-south"]}),

    # Security
    ("okta", "login.failed", {"user": "admin@company.com", "ip": "203.0.113.42", "reason": "invalid_credentials", "attempts": 5}),
    ("okta", "login.failed", {"user": "cto@company.com", "ip": "198.51.100.77", "reason": "mfa_timeout", "attempts": 2}),
    ("okta", "login.success", {"user": "dev@company.com", "ip": "10.0.1.15", "mfa": "totp"}),
    ("aws", "iam.policy_change", {"message": "IAM policy AdminAccess attached to role lambda-exec", "actor": "terraform", "account": "123456789"}),
    ("aws", "iam.key_created", {"message": "New access key created for service account ci-deploy", "account": "123456789"}),
    ("snyk", "vuln.detected", {"message": "Critical CVE-2024-3094 found in xz-utils 5.6.0", "package": "xz-utils", "severity": "critical", "cve": "CVE-2024-3094"}),
    ("snyk", "vuln.detected", {"message": "High severity prototype pollution in lodash < 4.17.21", "package": "lodash", "severity": "high", "cve": "CVE-2021-23337"}),
    ("cloudflare", "firewall.block", {"message": "Blocked 1,247 requests from AS13335 matching SQL injection rule", "rule_id": "cf-sqli-01", "blocked_count": 1247}),
    ("vault", "secret.accessed", {"message": "Secret database/creds/readonly accessed by auth-service", "path": "database/creds/readonly", "accessor": "auth-service"}),

    # Alerts
    ("pagerduty", "incident.triggered", {"message": "API error rate exceeded 5% threshold", "service": "api-gateway", "urgency": "high"}),
    ("pagerduty", "incident.resolved", {"message": "API error rate returned to normal (0.3%)", "service": "api-gateway", "resolution_time": "12m"}),
    ("opsgenie", "alert.fired", {"message": "PostgreSQL replication lag > 30s on replica-2", "team": "platform", "priority": "P1"}),
    ("opsgenie", "alert.fired", {"message": "Redis memory usage at 92% on cache-prod-01", "team": "platform", "priority": "P2"}),
    ("sentry", "error.new", {"message": "TypeError: Cannot read property 'id' of undefined", "project": "frontend", "users_affected": 142, "url": "/dashboard/settings"}),
    ("sentry", "error.new", {"message": "ConnectionRefusedError: [Errno 111] Connection refused", "project": "api-gateway", "users_affected": 89}),
    ("sentry", "error.regression", {"message": "NullPointerException in PaymentProcessor.charge()", "project": "payment-service", "first_seen": "2024-01-15", "count": 47}),
    ("statuspage", "incident.created", {"message": "Investigating elevated error rates on API", "component": "API", "status": "investigating"}),
    ("statuspage", "incident.resolved", {"message": "API error rates resolved - root cause was a bad deploy", "component": "API", "status": "resolved"}),

    # Metrics
    ("datadog", "metric.threshold", {"message": "p99 latency exceeded 500ms on api-gateway", "metric": "trace.http.request.duration.p99", "value": 782, "threshold": 500}),
    ("datadog", "metric.threshold", {"message": "CPU usage at 94% on worker-prod-03", "metric": "system.cpu.user", "value": 94, "threshold": 85, "host": "worker-prod-03"}),
    ("datadog", "metric.anomaly", {"message": "Anomalous drop in request throughput detected", "metric": "http.requests.count", "expected": 1200, "actual": 340}),
    ("prometheus", "alert.firing", {"message": "SLO burn rate critical: error budget consumed 80% in 1h", "alertname": "SLOBurnRate", "slo": "api-availability", "burn_rate": 14.2}),
    ("prometheus", "alert.firing", {"message": "Disk usage above 90% on /data volume", "alertname": "DiskSpaceLow", "instance": "db-prod-01", "usage_pct": 93}),
    ("grafana", "alert.state_change", {"message": "Memory usage returned to normal on cache-prod-01", "from": "alerting", "to": "ok", "dashboard": "Infrastructure"}),
    ("cloudwatch", "alarm.triggered", {"message": "Lambda cold starts exceeded 200/min", "alarm": "LambdaColdStarts", "function": "api-authorizer", "value": 347}),
    ("newrelic", "metric.alert", {"message": "Apdex score dropped below 0.85 on frontend", "apdex": 0.72, "app": "frontend", "throughput": 4500}),

    # Info
    ("jira", "issue.created", {"description": "Implement user preference API endpoint", "key": "PLAT-482", "type": "Story", "assignee": "alice"}),
    ("jira", "issue.transitioned", {"description": "Fix flaky test in auth module", "key": "PLAT-471", "from": "In Progress", "to": "Done"}),
    ("jira", "issue.created", {"description": "Upgrade PostgreSQL from 15 to 16", "key": "PLAT-490", "type": "Task", "assignee": "bob"}),
    ("slack", "message.posted", {"message": "Heads up: maintenance window tonight 2am-4am UTC", "channel": "#engineering", "author": "platform-bot"}),
    ("slack", "message.posted", {"message": "Retrospective notes posted for last week's incident", "channel": "#incidents", "author": "alice"}),
    ("confluence", "page.updated", {"message": "Updated runbook: Database failover procedure", "space": "Engineering", "author": "bob"}),
    ("terraform", "plan.complete", {"message": "Terraform plan: 3 to add, 1 to change, 0 to destroy", "workspace": "production", "changes": {"add": 3, "change": 1, "destroy": 0}}),
    ("kubernetes", "pod.restarted", {"message": "Pod api-gateway-7f8b9c-x2k4j restarted (OOMKilled)", "namespace": "production", "restart_count": 3}),
    ("kubernetes", "node.ready", {"message": "Node pool scaled up: 4 -> 6 nodes in us-east-1", "pool": "general", "reason": "HPA target exceeded"}),
]


class Command(BaseCommand):
    help = "Seed database with realistic demo events, API keys, and an admin user"

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush", action="store_true", help="Delete existing events and keys first"
        )

    def handle(self, *args, **options):
        if options["flush"]:
            Event.objects.all().delete()
            ApiKey.objects.all().delete()
            self.stdout.write("Flushed existing events and keys.")

        # Admin user
        admin, created = User.objects.get_or_create(
            username="admin",
            defaults={"email": "admin@observaboard.dev", "is_staff": True, "is_superuser": True},
        )
        if created:
            admin.set_password("admin")
            admin.save()
            self.stdout.write(self.style.SUCCESS("Created admin user (admin / admin)"))
        else:
            self.stdout.write("Admin user already exists.")

        # API keys
        key_names = ["ci-pipeline", "grafana-webhook", "production-ingest"]
        for name in key_names:
            key, created = ApiKey.objects.get_or_create(name=name)
            if created:
                self.stdout.write(f"  Created API key: {name} ({key.key[:8]}...)")

        # Create a revoked key for visual variety
        revoked, created = ApiKey.objects.get_or_create(
            name="old-staging-key",
            defaults={"is_active": False},
        )
        if created:
            self.stdout.write("  Created revoked key: old-staging-key")

        # Events spread over the last 7 days
        now = timezone.now()
        events_created = 0

        for _i, (source, event_type, payload) in enumerate(SCENARIOS):
            # Spread events across the last 7 days with some randomness
            hours_ago = random.uniform(0, 168)  # 7 days in hours
            created_at = now - timedelta(hours=hours_ago)

            category, severity, summary = _classify(source, event_type, payload)

            event = Event(
                source=source,
                event_type=event_type,
                raw_payload=payload,
                classified=True,
                category=category,
                severity=severity,
                summary=summary,
            )
            event.save()
            # Backdate created_at (auto_now_add prevents setting it in constructor)
            Event.objects.filter(pk=event.pk).update(created_at=created_at)
            events_created += 1

        # Add some duplicate scenarios with slight time variation for volume
        extras = random.choices(SCENARIOS, k=20)
        for source, event_type, payload in extras:
            hours_ago = random.uniform(0, 168)
            created_at = now - timedelta(hours=hours_ago)

            category, severity, summary = _classify(source, event_type, payload)
            event = Event(
                source=source,
                event_type=event_type,
                raw_payload=payload,
                classified=True,
                category=category,
                severity=severity,
                summary=summary,
            )
            event.save()
            Event.objects.filter(pk=event.pk).update(created_at=created_at)
            events_created += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nSeeded {events_created} events across {len({s[0] for s in SCENARIOS})} sources."
        ))
        self.stdout.write("Login at /dashboard/ with admin / admin")
