"""Run a bounded owner passwordless mail outbox batch."""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from core.owner_mail_worker import dispatch_one, worker_enabled


class Command(BaseCommand):
    help = "Dispatch at most N owner email challenges"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=5)
        parser.add_argument("--confirm", required=True)

    def handle(self, *args, **options):
        confirmation = "SEND-PRODUCTION-OWNER-MAIL" if settings.IS_PRODUCTION else "SEND-STAGING-OWNER-MAIL"
        if options["confirm"] != confirmation:
            raise CommandError("explicit owner mail confirmation required")
        if not worker_enabled():
            raise CommandError("owner mail delivery settings are disabled or invalid")
        limit = options["limit"]
        if not 1 <= limit <= 20:
            raise CommandError("limit must be between 1 and 20")
        results: dict[str, int] = {}
        for _ in range(limit):
            outcome = dispatch_one()
            results[outcome] = results.get(outcome, 0) + 1
            if outcome == "idle":
                break
        # Never output addresses, challenge IDs, generated links, or exceptions.
        self.stdout.write(
            "owner mail: " +
            ", ".join(f"{label}={count}" for label, count in sorted(results.items()))
        )
