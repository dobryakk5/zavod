from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0169_inbox_email_message"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="InboxReplyMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("thread_id", models.CharField(db_index=True, max_length=512)),
                ("channel", models.CharField(db_index=True, max_length=32)),
                ("direction", models.CharField(default="out", max_length=8)),
                ("contact_id", models.IntegerField(blank=True, db_index=True, null=True)),
                ("author", models.CharField(blank=True, default="", max_length=255)),
                ("text", models.TextField(blank=True, default="")),
                ("external_message_id", models.CharField(blank=True, default="", max_length=512)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("sent_at", models.DateTimeField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="inbox_reply_messages",
                        to="core.client",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="inbox_reply_messages_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-sent_at", "-id"),
            },
        ),
        migrations.AddIndex(
            model_name="inboxreplymessage",
            index=models.Index(fields=("client", "thread_id"), name="idx_inbox_reply_client_thread"),
        ),
        migrations.AddIndex(
            model_name="inboxreplymessage",
            index=models.Index(fields=("client", "channel"), name="idx_inbox_reply_client_channel"),
        ),
        migrations.AddIndex(
            model_name="inboxreplymessage",
            index=models.Index(fields=("client", "sent_at"), name="idx_inbox_reply_client_sent"),
        ),
    ]

