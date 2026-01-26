from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0116_weekly_content_strategy"),
    ]

    operations = [
        migrations.CreateModel(
            name="SemanticGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                (
                    "scope",
                    models.CharField(
                        blank=True,
                        choices=[("narrow", "Narrow"), ("normal", "Normal"), ("wide", "Wide")],
                        default="normal",
                        max_length=20,
                    ),
                ),
                ("expected_clusters", models.PositiveSmallIntegerField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("draft", "Draft"), ("approved", "Approved"), ("archived", "Archived")],
                        default="draft",
                        max_length=20,
                    ),
                ),
                (
                    "source",
                    models.CharField(
                        choices=[("ai", "AI"), ("manual", "Manual")],
                        default="ai",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="semantic_groups",
                        to="core.client",
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="children",
                        to="core.semanticgroup",
                    ),
                ),
            ],
            options={
                "verbose_name": "Semantic Group",
                "verbose_name_plural": "Semantic Groups",
                "db_table": "semantic_groups",
                "ordering": ("-created_at",),
                "indexes": [
                    models.Index(fields=["client", "status"], name="semgrp_client_status_idx"),
                    models.Index(fields=["client", "created_at"], name="semgrp_client_created_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="SemanticPhrase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("phrase", models.TextField()),
                ("lemma", models.TextField(blank=True)),
                (
                    "type",
                    models.CharField(
                        choices=[("key", "Key"), ("lsi", "LSI")],
                        default="key",
                        max_length=20,
                    ),
                ),
                (
                    "intent",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("info", "Info"),
                            ("commercial", "Commercial"),
                            ("navigational", "Navigational"),
                            ("brand", "Brand"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("ai", "AI"),
                            ("wordstat", "Wordstat"),
                            ("gsc", "GSC"),
                            ("manual", "Manual"),
                            ("favorite", "Favorite"),
                        ],
                        default="ai",
                        max_length=20,
                    ),
                ),
                ("frequency", models.PositiveIntegerField(blank=True, null=True)),
                ("competition", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="semantic_phrases",
                        to="core.client",
                    ),
                ),
            ],
            options={
                "verbose_name": "Semantic Phrase",
                "verbose_name_plural": "Semantic Phrases",
                "db_table": "phrases",
                "ordering": ("-created_at",),
                "indexes": [
                    models.Index(fields=["client", "source"], name="semphr_client_source_idx"),
                    models.Index(fields=["client", "phrase"], name="semphr_client_phrase_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="SemanticCluster",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("main_keyword", models.CharField(blank=True, max_length=255)),
                (
                    "intent",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("info", "Info"),
                            ("commercial", "Commercial"),
                            ("navigational", "Navigational"),
                            ("brand", "Brand"),
                        ],
                        max_length=20,
                    ),
                ),
                ("user_goal", models.TextField(blank=True)),
                ("cta", models.CharField(blank=True, max_length=255)),
                ("priority", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("page_type", models.CharField(blank=True, max_length=50)),
                ("url", models.URLField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("planned", "Planned"), ("in_progress", "In progress"), ("published", "Published")],
                        default="planned",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="semantic_clusters",
                        to="core.client",
                    ),
                ),
                (
                    "semantic_group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="clusters",
                        to="core.semanticgroup",
                    ),
                ),
            ],
            options={
                "verbose_name": "Semantic Cluster",
                "verbose_name_plural": "Semantic Clusters",
                "db_table": "clusters",
                "ordering": ("-created_at",),
                "indexes": [
                    models.Index(fields=["client", "semantic_group"], name="semclust_client_group_idx"),
                    models.Index(fields=["client", "status"], name="semclust_client_status_idx"),
                    models.Index(fields=["client", "intent"], name="semclust_client_intent_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="ClusterPhrase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "role",
                    models.CharField(
                        choices=[("main", "Main"), ("support", "Support"), ("lsi", "LSI")],
                        default="support",
                        max_length=20,
                    ),
                ),
                ("weight", models.PositiveSmallIntegerField(blank=True, null=True)),
                (
                    "added_by",
                    models.CharField(
                        choices=[("ai", "AI"), ("manual", "Manual")],
                        default="ai",
                        max_length=20,
                    ),
                ),
                (
                    "cluster",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cluster_phrases",
                        to="core.semanticcluster",
                    ),
                ),
                (
                    "phrase",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cluster_phrases",
                        to="core.semanticphrase",
                    ),
                ),
            ],
            options={
                "verbose_name": "Cluster Phrase",
                "verbose_name_plural": "Cluster Phrases",
                "db_table": "cluster_phrases",
                "unique_together": {("cluster", "phrase")},
                "indexes": [
                    models.Index(fields=["cluster", "role"], name="clphr_cluster_role_idx"),
                    models.Index(fields=["phrase"], name="clphr_phrase_idx"),
                ],
            },
        ),
        migrations.AddField(
            model_name="semanticcluster",
            name="phrases",
            field=models.ManyToManyField(blank=True, related_name="clusters", through="core.ClusterPhrase", to="core.semanticphrase"),
        ),
    ]
