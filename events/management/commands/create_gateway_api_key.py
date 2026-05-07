"""Management command to provision an API key for the go-gateway mutation observer."""

from django.core.management.base import BaseCommand

from events.models import ApiKey


class Command(BaseCommand):
    help = "Create an API key for the go-gateway mutation observer."

    def add_arguments(self, parser):
        parser.add_argument(
            "--name",
            default="gateway",
            help="Descriptive name for the API key (default: gateway).",
        )
        parser.add_argument(
            "--idempotent",
            action="store_true",
            help="If a key with this name already exists, print its prefix and exit.",
        )

    def handle(self, *args, **options):
        name = options["name"]

        if options["idempotent"]:
            existing = ApiKey.objects.filter(name=name).first()
            if existing:
                self.stdout.write(
                    self.style.WARNING(
                        f"API key '{name}' already exists (prefix: {existing.prefix}). "
                        "Retrieve the raw key from Secret Manager."
                    )
                )
                return

        _, key = ApiKey.objects.create_key(name=name)
        self.stdout.write(self.style.SUCCESS(f"Created API key '{name}'."))
        self.stdout.write(f"Raw key: {key}")
        self.stdout.write(
            self.style.WARNING(
                "Store this key in Secret Manager as OBSERVABOARD_API_KEY immediately. "
                "It will not be shown again."
            )
        )
