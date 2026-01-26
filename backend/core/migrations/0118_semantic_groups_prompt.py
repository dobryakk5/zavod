from django.db import migrations


def add_semantic_groups_prompt(apps, schema_editor):
    GeneratorPrompt = apps.get_model("core", "GeneratorPrompt")
    GeneratorPrompt.objects.update_or_create(
        code="semantic_groups_from_books",
        defaults={
            "group": "seo",
            "comment": "backend/core/ai_generator_content.py: ContentGenerationMixin.generate_semantic_groups_from_books",
            "prompt": """
Ты аналитик ниши и SEO-архитектор.

Тема проекта: $niche_text
Целевая аудитория: $audience_text
Описание продукта: $product_text

Источники знаний:
- Книги: $books_text
- (при наличии) Фрагменты или тексты: $fragments_text

Задача:
Разбить тематику проекта на СМЫСЛОВЫЕ ГРУППЫ
для таблицы semantic_groups.

Требования:

1. Делить по СМЫСЛУ и ПРЕДМЕТУ,
   а не по:
   - типу запроса (коммерческий / инфо)
   - формату контента (статья / лендинг)
   - этапу воронки
   - SEO-ключам

2. Каждая смысловая группа должна быть:
   - логически цельной
   - не слишком широкой
   - не слишком узкой
   - внутри неё должно помещаться от 5 до 30 SEO-кластеров

3. Не дроби одну тему на несколько групп,
   если внутри неё просто разные интенты.

4. Не объединяй разные темы в одну группу,
   даже если по ним похожие запросы.

5. Ориентир по количеству групп:
   - узкая ниша: 5–12
   - средняя ниша: 8–20
   - широкая ниша: 15–40

Сделай:

   Список смысловых групп в формате,
   пригодном для записи в БД:

   Для каждой группы:

   - name: короткое человеческое название
   - description:
       что именно входит в эту группу
       и что в неё НЕ входит
   - scope: narrow / normal / wide
   - expected_clusters:
       сколько SEO-кластеров логично внутри
   - examples:
       5–10 примеров под-тем, вопросов или интентов,
       которые должны попадать в эту группу

Перед финальным ответом:

1. Проверь:
   - нет ли двух групп про одно и то же разными словами
   - нет ли слишком узких групп (1–2 возможных интента)
   - нет ли слишком широких групп (50+ интентов)

2. Если есть:
   - объедини
   - укрупни
   - переименуй

ФОРМАТ ОТВЕТА, СТРОГО JSON:
{
  "groups": [
    {
      "name": "Название",
      "description": "Что входит и что не входит",
      "scope": "narrow|normal|wide",
      "expected_clusters": 12,
      "examples": ["пример 1", "пример 2"]
    }
  ]
}

Верни только JSON, без пояснений.
""",
        },
    )


def remove_semantic_groups_prompt(apps, schema_editor):
    GeneratorPrompt = apps.get_model("core", "GeneratorPrompt")
    GeneratorPrompt.objects.filter(code="semantic_groups_from_books").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0117_semantic_groups_clusters_phrases"),
    ]

    operations = [
        migrations.RunPython(add_semantic_groups_prompt, reverse_code=remove_semantic_groups_prompt),
    ]
