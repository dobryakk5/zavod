from django.db import migrations


UPDATED_PROMPT = """
$language_note

Ты профессиональный SEO-специалист по Яндексу.

Ниша: $niche_value
Продукт/услуга: $product_value
ЦА: $audience_value

Сгенерируй список базовых поисковых запросов (seed keywords),
которые:
- короткие (1–4 слова)
- отражают суть ниши
- могут использоваться как отправная точка для Wordstat
- не являются длинными хвостами

Раздели их по группам (по три высокочастотных фразы на группу):
1) Коммерческие
2) Категорийные
3) Проблемные
4) Альтернативные формулировки

Не используй года, города и уточнения.

Ответ верни строго в JSON по схеме:
{
  "Коммерческие": ["...", "...", "..."],
  "Категорийные": ["...", "...", "..."],
  "Проблемные": ["...", "...", "..."],
  "Альтернативные формулировки": ["...", "...", "..."]
}
"""


def update_prompt(apps, schema_editor):
    GeneratorPrompt = apps.get_model("core", "GeneratorPrompt")
    GeneratorPrompt.objects.filter(code="seo_wordstat_seed_groups").update(
        prompt=UPDATED_PROMPT.strip()
    )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0107_generator_prompts"),
    ]

    operations = [
        migrations.RunPython(update_prompt, reverse_code=migrations.RunPython.noop),
    ]
