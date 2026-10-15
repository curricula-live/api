"""Explicit staging-only batch cleanup; never sends sign-in emails."""
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from core.owner_mail_maintenance import maintenance_enabled, sweep_owner_mail


class Command(BaseCommand):
    help = "Prune expired owner login jobs and old rate-limit buckets in staging."

    def add_arguments(self, parser):
        parser.add_argument("--batch", type=int, default=100)
        parser.add_argument("--confirm", required=True)

    def handle(self, *args, **options):
        confirmation = "MAINTAIN-PRODUCTION-OWNER-MAIL" if settings.IS_PRODUCTION else "MAINTAIN-STAGING-OWNER-MAIL"
        if options["confirm"] != confirmation:
            raise CommandError("explicit owner cleanup confirmation required")
        if not maintenance_enabled():
            raise CommandError("owner mail cleanup is disabled")
        if not 1 <= options["batch"] <= 1000:
            raise CommandError("batch must be between 1 and 1000")
        discarded, pruned = sweep_owner_mail(batch=options["batch"])
        self.stdout.write(f"owner mail cleanup: discarded={discarded}, old_buckets={pruned}")
