import sqlite3
from contextlib import closing
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import connection, transaction

from core.models import Client, ContentTemplate, UserTenantRole


class Command(BaseCommand):
    help = (
        "Import users, clients, content templates, and user/client role bindings "
        "from the legacy SQLite database."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--sqlite-path",
            default=str(settings.BASE_DIR / "db.sqlite3"),
            help="Path to the SQLite file you want to migrate data from.",
        )

    def handle(self, *args, **options):
        sqlite_path = Path(options["sqlite_path"]).expanduser().resolve()

        if not sqlite_path.exists():
            raise CommandError(f"SQLite database not found at {sqlite_path}")

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
            template_table_info = conn.execute(
                "PRAGMA table_info('core_contenttemplate')"
            ).fetchall()
            template_column_names = {col["name"] for col in template_table_info}
            template_select_parts = [
                "id",
                "name",
                "tone",
                "length",
                "language",
            ]
            if "seo_prompt_template" in template_column_names:
                template_select_parts.append("seo_prompt_template")
            if "trend_prompt_template" in template_column_names:
                template_select_parts.append("trend_prompt_template")
            if "prompt_template" in template_column_names:
                template_select_parts.append("prompt_template AS legacy_prompt_template")
            template_select_parts.extend([
                "additional_instructions",
                "is_default",
                "include_hashtags",
                "max_hashtags",
                "client_id",
                "type",
            ])
            template_rows = conn.execute(
                f"SELECT {', '.join(template_select_parts)} FROM core_contenttemplate"
            ).fetchall()
            role_rows = conn.execute(
                "SELECT id, role, client_id, user_id FROM core_usertenantrole"
            ).fetchall()

        User = get_user_model()

        with transaction.atomic():
            user_stats = self._import_users(User, user_rows)
            client_stats = self._import_clients(client_rows)
            template_stats = self._import_templates(template_rows)
            role_stats = self._import_roles(role_rows, User)
            self._reset_sequences([User, Client, ContentTemplate, UserTenantRole])

        self.stdout.write(
            self.style.SUCCESS("Users imported: %s new / %s updated" % user_stats)
        )
        self.stdout.write(
            self.style.SUCCESS("Clients imported: %s new / %s updated" % client_stats)
        )
        template_msg = (
            "Content templates imported: %(created)s new / %(updated)s updated"
            % template_stats
        )
        if template_stats["skipped"]:
            template_msg += f" (skipped {template_stats['skipped']} due to missing clients)"
        self.stdout.write(self.style.SUCCESS(template_msg))
        role_msg = (
            "Roles imported: %(created)s new / %(updated)s updated"
            % role_stats
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
            user_data = {
                "email": row["email"] or "",
                "password": row["password"],
                "is_superuser": bool(row["is_superuser"]),
                "is_staff": bool(row["is_staff"]),
                "is_active": bool(row["is_active"]),
                "first_name": row["first_name"] or "",
                "last_name": row["last_name"] or "",
            }
            user_id = row["id"]
            username = row["username"]

            obj = User.objects.filter(id=user_id).first()
            if obj:
                self._update_user_instance(obj, username, user_data)
                updated += 1
                continue

            obj = User.objects.filter(username=username).first()
            if obj:
                self._update_user_instance(obj, username, user_data)
                updated += 1
                continue

            User.objects.create(id=user_id, username=username, **user_data)
            created += 1

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

    def _import_templates(self, rows):
        created = 0
        updated = 0
        skipped = 0

        if not rows:
            self.stdout.write(self.style.WARNING("No content templates found in SQLite database."))
            return {"created": created, "updated": updated, "skipped": skipped}

        for row in rows:
            if not Client.objects.filter(id=row["client_id"]).exists():
                skipped += 1
                continue

            row_keys = row.keys()
            legacy_prompt = row["legacy_prompt_template"] if "legacy_prompt_template" in row_keys else ""
            seo_prompt = row["seo_prompt_template"] if "seo_prompt_template" in row_keys else ""
            trend_prompt = row["trend_prompt_template"] if "trend_prompt_template" in row_keys else ""

            defaults = {
                "client_id": row["client_id"],
                "name": row["name"],
                "tone": row["tone"] or "professional",
                "length": row["length"] or "medium",
                "language": row["language"] or "ru",
                "seo_prompt_template": (seo_prompt or legacy_prompt or ""),
                "trend_prompt_template": trend_prompt or "",
                "additional_instructions": row["additional_instructions"] or "",
                "is_default": bool(row["is_default"]),
                "include_hashtags": bool(row["include_hashtags"]),
                "max_hashtags": row["max_hashtags"] or 5,
                "type": row["type"] or "selling",
            }
            _, was_created = ContentTemplate.objects.update_or_create(
                id=row["id"],
                defaults=defaults,
            )
            if was_created:
                created += 1
            else:
                updated += 1

        return {"created": created, "updated": updated, "skipped": skipped}

    def _import_roles(self, rows, User):
        created = 0
        updated = 0
        skipped = 0

        if not rows:
            self.stdout.write(
                self.style.WARNING("No user/client role bindings found in SQLite database.")
            )
            return {"created": created, "updated": updated, "skipped": skipped}

        for row in rows:
            if not User.objects.filter(id=row["user_id"]).exists() or not Client.objects.filter(
                id=row["client_id"]
            ).exists():
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

    def _update_user_instance(self, obj, username, fields):
        for attr, value in fields.items():
            setattr(obj, attr, value)
        obj.username = username
        obj.save()
