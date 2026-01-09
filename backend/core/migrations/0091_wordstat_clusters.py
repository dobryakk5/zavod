from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0090_website_scan_page_clusters"),
    ]

    operations = [
        migrations.CreateModel(
            name="WordstatCluster",
            fields=[
                ("id", models.SmallAutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="wordstat_clusters",
                        to="core.client",
                    ),
                ),
            ],
            options={
                "verbose_name": "Wordstat Cluster",
                "verbose_name_plural": "Wordstat Clusters",
                "ordering": ("name", "id"),
            },
        ),
        migrations.AddField(
            model_name="wordstatresult",
            name="cluster",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="results",
                to="core.wordstatcluster",
            ),
        ),
        migrations.AddIndex(
            model_name="wordstatcluster",
            index=models.Index(
                fields=["client", "name"],
                name="ws_cluster_client_name_idx",
            ),
        ),
    ]
