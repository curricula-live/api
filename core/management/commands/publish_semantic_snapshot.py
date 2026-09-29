from django.core.management.base import BaseCommand, CommandError

from core.semantic import SnapshotConflict, SnapshotCycle, publish_snapshot


class Command(BaseCommand):
    help = "Publish an immutable prerequisite snapshot from the current canonical graph."

    def add_arguments(self, parser):
        parser.add_argument("snapshot_id")

    def handle(self, *args, **options):
        try:
            snapshot, created = publish_snapshot(options["snapshot_id"])
        except (SnapshotConflict, SnapshotCycle, ValueError) as exc:
            raise CommandError(str(exc)) from exc

        action = "Published" if created else "Verified existing"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} {snapshot.snapshot_id} {snapshot.content_hash}"
            )
        )
