from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0168_contact_service_packages"),
    ]

    operations = [
        migrations.CreateModel(
            name="InboxEmailMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(blank=True, default="email", max_length=64)),
                ("source", models.CharField(blank=True, default="webhook", max_length=64)),
                ("external_message_id", models.CharField(blank=True, default="", max_length=512)),
                ("thread_key", models.CharField(blank=True, db_index=True, default="", max_length=512)),
                ("from_name", models.CharField(blank=True, default="", max_length=255)),
                ("from_email", models.EmailField(blank=True, db_index=True, default="", max_length=254)),
                ("to_email", models.EmailField(blank=True, default="", max_length=254)),
                ("subject", models.CharField(blank=True, default="", max_length=500)),
                ("body_text", models.TextField(blank=True, default="")),
                ("body_html", models.TextField(blank=True, default="")),
                ("contact_id", models.IntegerField(blank=True, db_index=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("received_at", models.DateTimeField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="inbox_email_messages",
                        to="core.client",
                    ),
                ),
            ],
            options={
                "ordering": ("-received_at", "-id"),
            },
        ),
        migrations.AddIndex(
            model_name="inboxemailmessage",
            index=models.Index(fields=("client", "received_at"), name="idx_inbox_email_client_received"),
        ),
        migrations.AddIndex(
            model_name="inboxemailmessage",
            index=models.Index(fields=("client", "thread_key"), name="idx_inbox_email_client_thread"),
        ),
        migrations.AddIndex(
            model_name="inboxemailmessage",
            index=models.Index(fields=("client", "from_email"), name="idx_inbox_email_client_from"),
        ),
        migrations.AddIndex(
            model_name="inboxemailmessage",
            index=models.Index(fields=("client", "external_message_id"), name="idx_inbox_email_client_extmsg"),
        ),
    ]

