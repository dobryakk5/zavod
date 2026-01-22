from django.db import migrations


PROMPTS = [
    {
        "code": "tgstat_recommendations",
        "comment": "backend/core/ai_generator_content.py: ContentGenerationMixin.generate_tgstat_tag_recommendations",
        "group": "service",
        "prompt": """
Ты — аналитик Telegram-каналов и каталога TGStat.
Ниша: $niche_value
Продукт/услуга: $product_value
Язык ответа: $lang_name

Ниже список категорий TGStat и их подкатегорий в формате JSON.
Используй только эти данные. Не придумывай новых подкатегорий.

Список:
$categories_json

Задача:
- Для данной ниши и продукта выбери релевантные подкатегории.
- Сгруппируй рекомендации по категориям.
- Для каждой выбранной категории верни 3-7 подкатегорий (если релевантно).
- Если категория не подходит — не возвращай ее.

Ответ строго JSON в формате:
{
  "recommendations": [
    {
      "category_slug": "string",
      "category_title": "string",
      "tags": [
        {"slug": "string", "title": "string", "reason": "string"}
      ]
    }
  ]
}

Правила:
- Используй только `slug` и `title` из списка.
- `reason` — короткое объяснение (1 фраза) почему подкатегория подходит, можно оставить пустой строкой.
- Не добавляй никакого текста кроме JSON.
""",
    },
]


def create_tgstat_prompts(apps, schema_editor):
    GeneratorPrompt = apps.get_model("core", "GeneratorPrompt")
    for item in PROMPTS:
        prompt_text = (item.get("prompt") or "").strip()
        GeneratorPrompt.objects.update_or_create(
            code=item["code"],
            defaults={
                "prompt": prompt_text,
                "comment": item.get("comment", ""),
                "group": item.get("group", "posts"),
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0109_generator_prompt_groups"),
    ]

    operations = [
        migrations.RunPython(create_tgstat_prompts, reverse_code=migrations.RunPython.noop),
    ]
