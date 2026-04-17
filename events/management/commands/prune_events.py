"""Management command to delete old events beyond a configurable retention window."""
import logging

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from events.models import Event

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Delete events older than DAYS days (default: 90)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=90,
            help="Retain events newer than this many days (default: 90).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Print the count of events that would be deleted without deleting them.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        if days < 1:
            raise CommandError("--days must be a positive integer.")

        cutoff = timezone.now() - timezone.timedelta(days=days)
        qs = Event.objects.filter(created_at__lt=cutoff)
        count = qs.count()

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    f"[dry-run] Would delete {count} event(s) older than {days} day(s) (before {cutoff.date()})."
                )
            )
            return

        deleted, _ = qs.delete()
        logger.info("prune_events: deleted %d event(s) older than %d day(s)", deleted, days)
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted} event(s) older than {days} day(s) (before {cutoff.date()})."
            )
        )
