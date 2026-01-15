from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0099_client_plan"),
    ]

    operations = [
        migrations.CreateModel(
            name="GenerationEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(choices=[("post", "Post generation"), ("article_write", "Article write"), ("article_evaluate", "Article evaluate"), ("channel_analysis", "Channel analysis"), ("website_analysis", "Website analysis"), ("weekly_collection", "Weekly collections"), ("seo_group", "SEO groups"), ("wordstat_query", "Wordstat query"), ("google_query", "Google query"), ("product", "Product generation"), ("product_map", "Product map"), ("book_search", "Book search")], max_length=32)),
                ("meta", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("client", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="generation_events", to="core.client")),
            ],
            options={
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddIndex(
            model_name="generationevent",
            index=models.Index(fields=["client", "event_type", "-created_at"], name="gen_ev_client_type_created"),
        ),
    ]
