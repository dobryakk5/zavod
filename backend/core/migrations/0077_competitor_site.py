from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0076_website_scan_page_is_helper"),
    ]

    operations = [
        migrations.CreateModel(
            name="CompetitorSite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("domain", models.CharField(max_length=255)),
                ("base_url", models.CharField(blank=True, default="", max_length=500)),
                ("first_seen_query", models.CharField(blank=True, default="", max_length=512)),
                ("last_seen_query", models.CharField(blank=True, default="", max_length=512)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("client", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="competitor_sites", to="core.client")),
            ],
            options={
                "ordering": ("-updated_at",),
            },
        ),
        migrations.AddConstraint(
            model_name="competitorsite",
            constraint=models.UniqueConstraint(fields=("client", "domain"), name="uniq_competitor_site_client_domain"),
        ),
        migrations.AddIndex(
            model_name="competitorsite",
            index=models.Index(fields=["client", "domain"], name="comp_site_client_domain_idx"),
        ),
        migrations.AddIndex(
            model_name="competitorsite",
            index=models.Index(fields=["client", "-updated_at"], name="comp_site_client_updated_idx"),
        ),
    ]

