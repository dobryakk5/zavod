import sqlite3
from contextlib import closing
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Import users from the legacy SQLite auth_user table into the active DB."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sqlite-path",
            default=str(settings.BASE_DIR / "db.sqlite3"),
            help="Path to the SQLite file you want to migrate users from.",
        )

    def handle(self, *args, **options):
        sqlite_path = Path(options["sqlite_path"]).expanduser().resolve()

        if not sqlite_path.exists():
            raise CommandError(f"SQLite database not found: {sqlite_path}")

        with closing(sqlite3.connect(str(sqlite_path))) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT username, email, password, is_superuser, "
                "is_staff, is_active, first_name, last_name FROM auth_user"
            ).fetchall()

        if not rows:
            self.stdout.write(self.style.WARNING("No users found in SQLite database."))
            return

        User = get_user_model()
        created = 0
        updated = 0

        with transaction.atomic():
            for row in rows:
                defaults = {
                    "email": row["email"] or "",
                    "password": row["password"],
                    "is_superuser": bool(row["is_superuser"]),
                    "is_staff": bool(row["is_staff"]),
                    "is_active": bool(row["is_active"]),
                    "first_name": row["first_name"] or "",
                    "last_name": row["last_name"] or "",
                }
                _, was_created = User.objects.update_or_create(
                    username=row["username"],
                    defaults=defaults,
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {created} new user(s) and updated {updated} existing user(s)."
            )
        )
