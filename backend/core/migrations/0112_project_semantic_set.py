from django.db import migrations, models
import django.db.models.deletion


def add_project_semantics_prompt(apps, schema_editor):
    GeneratorPrompt = apps.get_model("core", "GeneratorPrompt")
    GeneratorPrompt.objects.update_or_create(
        code="project_semantics_from_books",
        defaults={
            "group": "seo",
            "comment": "backend/core/ai_generator_content.py: ContentGenerationMixin.generate_project_semantics_from_books",
            "prompt": """
Ты — SEO-стратег и редактор семантики.

БРЕНД/ПРОЕКТ: $brand_text

Список книг экспертов (1 книга на строку):
$books_text

ЗАДАЧА
Сформируй семантику проекта на основе тем и идей из этих книг для будущих SEO-статей.

ТРЕБОВАНИЯ
- 6–10 тематических кластеров.
- В каждом кластере 6–12 поисковых фраз.
- Фразы похожи на реальные поисковые запросы.
- Пиши на $lang_name языке.

ФОРМАТ ОТВЕТА, СТРОГО JSON:
{
  "groups": [
    {"name": "Название кластера", "phrases": ["фраза 1", "фраза 2"]}
  ],
  "keywords": ["ключ 1", "ключ 2"]
}

Верни только JSON, без пояснений.
""",
        },
    )


def remove_project_semantics_prompt(apps, schema_editor):
    GeneratorPrompt = apps.get_model("core", "GeneratorPrompt")
    GeneratorPrompt.objects.filter(code="project_semantics_from_books").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0111_wordstat_association_prompt"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectSemanticSet",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "source",
                    models.CharField(
                        choices=[("expert_books", "Expert books")],
                        default="expert_books",
                        max_length=32,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Ожидает генерации"),
                            ("generating", "Генерируется"),
                            ("completed", "Завершено"),
                            ("failed", "Ошибка"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                (
                    "books_text",
                    models.TextField(
                        blank=True,
                        help_text="Книги экспертов, использованные для генерации",
                    ),
                ),
                ("keyword_groups", models.JSONField(blank=True, default=dict)),
                ("keywords_list", models.JSONField(blank=True, default=list)),
                ("ai_model", models.CharField(blank=True, max_length=100)),
                ("prompt_used", models.TextField(blank=True)),
                ("error_log", models.TextField(blank=True)),
                ("raw_response", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="semantic_sets",
                        to="core.client",
                    ),
                ),
            ],
            options={
                "verbose_name": "Project Semantic Set",
                "verbose_name_plural": "Project Semantic Sets",
                "ordering": ("-created_at",),
            },
        ),
        migrations.RunPython(add_project_semantics_prompt, reverse_code=remove_project_semantics_prompt),
    ]
