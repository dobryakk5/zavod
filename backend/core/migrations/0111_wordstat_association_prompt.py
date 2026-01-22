from django.db import migrations


PROMPTS = [
    {
        "code": "seo_wordstat_top_associations",
        "comment": "backend/core/ai_generator_seo.py: select_wordstat_association_seeds",
        "group": "wordstat",
        "prompt": """
$language_note

Ты профессиональный SEO-специалист по Яндексу.

Ниша: $niche_value
Продукт/услуга: $product_value
ЦА: $audience_value
Группа: $group_name

Ниже ассоциации Wordstat с частотностью (топ $associations_count).
Выбери 3 фразы, которые:
- максимально подходят нише и продукту
- находятся среди самых частотных (ориентируйся на count)
- не дублируют друг друга и не слишком общие

Список (JSON):
$associations_json

Ответ верни строго в JSON по схеме:
{
  "phrases": ["...", "...", "..."]
}
""",
    },
]


def create_wordstat_association_prompt(apps, schema_editor):
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
        ("core", "0110_tgstat_recommendations_prompt"),
    ]

    operations = [
        migrations.RunPython(create_wordstat_association_prompt, reverse_code=migrations.RunPython.noop),
    ]
