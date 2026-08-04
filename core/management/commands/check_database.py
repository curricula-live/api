from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connections


class Command(BaseCommand):
    help = "Verify the default database connection using a read-only SQL query."

    def handle(self, *args, **options):
        database_connection = connections["default"]

        try:
            with database_connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        current_database(),
                        current_user,
                        current_schema(),
                        version();
                    """
                )
                database, user, schema, server_version = cursor.fetchone()
        except DatabaseError as exc:
            raise CommandError(f"Database connectivity check failed: {exc}") from exc

        self.stdout.write(self.style.SUCCESS("Database connection succeeded."))
        self.stdout.write(f"Database: {database}")
        self.stdout.write(f"User: {user}")
        self.stdout.write(f"Schema: {schema}")
        self.stdout.write(f"Server: {server_version}")
