import sqlite3
from contextlib import closing
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import connection, transaction

from core.models import Client, UserTenantRole


class Command(BaseCommand):
    help = "Import users, clients, and their roles from the legacy SQLite database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sqlite-path",
            default=str(settings.BASE_DIR / "db.sqlite3"),
            help="Path to the SQLite file you want to migrate data from.",
        )

    def handle(self, *args, **options):
        sqlite_path = Path(options["sqlite_path"]).expanduser().resolve()

        if not sqlite_path.exists():
            raise CommandError(f"SQLite database not found: {sqlite_path}")

        with closing(sqlite3.connect(str(sqlite_path))) as conn:
            conn.row_factory = sqlite3.Row
            user_rows = conn.execute(
                "SELECT id, username, email, password, is_superuser, "
                "is_staff, is_active, first_name, last_name "
                "FROM auth_user"
            ).fetchall()
            client_rows = conn.execute(
                "SELECT id, name, slug, timezone, telegram_api_hash, telegram_api_id, "
                "telegram_source_channels, instagram_access_token, instagram_source_accounts, "
                "rss_source_feeds, youtube_api_key, youtube_source_channels, "
                "vkontakte_access_token, vkontakte_source_groups, avatar, desires, "
                "objections, pains "
                "FROM core_client"
            ).fetchall()
            role_rows = conn.execute(
                "SELECT id, role, client_id, user_id FROM core_usertenantrole"
            ).fetchall()

        User = get_user_model()

        with transaction.atomic():
            user_stats = self._import_users(User, user_rows)
            client_stats = self._import_clients(client_rows)
            role_stats = self._import_roles(role_rows, User)
            self._reset_sequences([User, Client, UserTenantRole])

        self.stdout.write(
            self.style.SUCCESS(
                "Users imported: %s new / %s updated" % user_stats
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Clients imported: %s new / %s updated" % client_stats
            )
        )
        role_msg = (
            f"Roles imported: {role_stats['created']} new / {role_stats['updated']} updated"
        )
        if role_stats["skipped"]:
            role_msg += f" (skipped {role_stats['skipped']} because of missing users/clients)"
        self.stdout.write(self.style.SUCCESS(role_msg))

    def _import_users(self, User, rows):
        created = 0
        updated = 0

        if not rows:
            self.stdout.write(self.style.WARNING("No users found in SQLite database."))
            return created, updated

        for row in rows:
            defaults = {
                "username": row["username"],
                "email": row["email"] or "",
                "password": row["password"],
                "is_superuser": bool(row["is_superuser"]),
                "is_staff": bool(row["is_staff"]),
                "is_active": bool(row["is_active"]),
                "first_name": row["first_name"] or "",
                "last_name": row["last_name"] or "",
            }
            _, was_created = User.objects.update_or_create(
                id=row["id"],
                defaults=defaults,
            )
            if was_created:
                created += 1
            else:
                updated += 1

        return created, updated

    def _import_clients(self, rows):
        created = 0
        updated = 0

        if not rows:
            self.stdout.write(self.style.WARNING("No clients found in SQLite database."))
            return created, updated

        for row in rows:
            defaults = {
                "name": row["name"],
                "slug": row["slug"],
                "timezone": row["timezone"] or "UTC",
                "telegram_api_hash": row["telegram_api_hash"] or "",
                "telegram_api_id": row["telegram_api_id"] or "",
                "telegram_source_channels": row["telegram_source_channels"] or "",
                "instagram_access_token": row["instagram_access_token"] or "",
                "instagram_source_accounts": row["instagram_source_accounts"] or "",
                "rss_source_feeds": row["rss_source_feeds"] or "",
                "youtube_api_key": row["youtube_api_key"] or "",
                "youtube_source_channels": row["youtube_source_channels"] or "",
                "vkontakte_access_token": row["vkontakte_access_token"] or "",
                "vkontakte_source_groups": row["vkontakte_source_groups"] or "",
                "avatar": row["avatar"] or "",
                "desires": row["desires"] or "",
                "objections": row["objections"] or "",
                "pains": row["pains"] or "",
            }
            _, was_created = Client.objects.update_or_create(
                id=row["id"],
                defaults=defaults,
            )
            if was_created:
                created += 1
            else:
                updated += 1

        return created, updated

    def _import_roles(self, rows, User):
        created = 0
        updated = 0
        skipped = 0

        if not rows:
            self.stdout.write(self.style.WARNING("No user/client role bindings found in SQLite database."))
            return {"created": created, "updated": updated, "skipped": skipped}

        for row in rows:
            user_exists = User.objects.filter(id=row["user_id"]).exists()
            client_exists = Client.objects.filter(id=row["client_id"]).exists()

            if not user_exists or not client_exists:
                skipped += 1
                continue

            _, was_created = UserTenantRole.objects.update_or_create(
                user_id=row["user_id"],
                client_id=row["client_id"],
                defaults={"role": row["role"]},
            )
            if was_created:
                created += 1
            else:
                updated += 1

        return {"created": created, "updated": updated, "skipped": skipped}

    def _reset_sequences(self, models):
        sql_list = connection.ops.sequence_reset_sql(no_style(), models)
        if not sql_list:
            return
        with connection.cursor() as cursor:
            for sql in sql_list:
                cursor.execute(sql)
