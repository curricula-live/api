"""Explicit staging-only batch cleanup; never sends sign-in emails."""
from django.core.management.base import BaseCommand, CommandError

from core.owner_mail_maintenance import maintenance_enabled, sweep_owner_mail


class Command(BaseCommand):
    help = "Prune expired owner login jobs and old rate-limit buckets in staging."

    def add_arguments(self, parser):
        parser.add_argument("--batch", type=int, default=100)
        parser.add_argument("--confirm", required=True)

    def handle(self, *args, **options):
        if options["confirm"] != "MAINTAIN-STAGING-OWNER-MAIL":
            raise CommandError("explicit staging owner cleanup confirmation required")
        if not maintenance_enabled():
            raise CommandError("owner mail cleanup is disabled outside staging")
        if not 1 <= options["batch"] <= 1000:
            raise CommandError("batch must be between 1 and 1000")
        discarded, pruned = sweep_owner_mail(batch=options["batch"])
        self.stdout.write(f"owner mail cleanup: discarded={discarded}, old_buckets={pruned}")
