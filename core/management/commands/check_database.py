from django.core.management.base import BaseCommand
from django.db import connections


class Command(BaseCommand):
    help = "Verify the default database connection using a read-only SQL query."

    def handle(self, *args, **options):
        database_connection = connections["default"]

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

        self.stdout.write(self.style.SUCCESS("Database connection succeeded."))
        self.stdout.write(f"Database: {database}")
        self.stdout.write(f"User: {user}")
        self.stdout.write(f"Schema: {schema}")
        self.stdout.write(f"Server: {server_version}")
