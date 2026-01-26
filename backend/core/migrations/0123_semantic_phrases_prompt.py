from django.db import migrations


def add_semantic_phrases_prompt(apps, schema_editor):
    GeneratorPrompt = apps.get_model("core", "GeneratorPrompt")
    GeneratorPrompt.objects.update_or_create(
        code="semantic_phrases_from_cluster",
        defaults={
            "group": "seo",
            "comment": "backend/core/ai_generator_content.py: ContentGenerationMixin.generate_semantic_phrases_from_cluster",
            "prompt": """
$language_note
Ты SEO-аналитик.

Тема проекта: $niche_text / $product_text

Смысловая группа:
- name: $group_name
- description: $group_description
- source_books: $group_source_books

SEO-кластер:
- name: $cluster_name
- description: $cluster_description
- main_keyword: $cluster_main_keyword
- intent: $cluster_intent
- user_goal: $cluster_user_goal
- cta: $cluster_cta

Задача:
Сгенерировать НАБОР SEO-ФРАЗ
для данного кластера
для таблицы `phrases` (type = key).

Требования:

1. Все фразы должны:
   - выражать ТОТ ЖЕ интент,
   - что и данный кластер,
   - быть пригодны для продвижения
     ОДНОЙ страницы.

2. Не включай фразы, если:
   - у них другой интент,
   - они требуют другого формата страницы.

3. Не генерируй:
   - SEO-синонимы без смысловой разницы,
   - перестановки слов без изменения смысла,
   - откровенный мусор.

4. Учитывай:
   - терминологию из source_books,
   - язык целевой аудитории.

5. Количество фраз:
   - 10–40 штук,
   - в зависимости от ширины интента.

Сделай:

Список фраз в формате,
пригодном для записи в БД.

Для каждой фразы:

- phrase:
    текст фразы

- type:
    key

- intent:
    $cluster_intent

- comment:
    почему эта фраза относится
    именно к этому кластеру

Перед финальным ответом:

1. Проверь:
   - нет ли фраз с другим интентом
   - нет ли дублей и почти-дублей
   - не слишком ли узкий набор (меньше 8 фраз)
   - не слишком ли широкий набор (больше 50 фраз)

2. Если есть:
   - удали
   - объедини
   - сократи

ФОРМАТ ОТВЕТА, СТРОГО JSON:
{
  "phrases": [
    {
      "phrase": "текст фразы",
      "type": "key",
      "intent": "info|commercial|navigational|brand",
      "comment": "пояснение"
    }
  ]
}

Верни только JSON, без пояснений.
""",
        },
    )


def remove_semantic_phrases_prompt(apps, schema_editor):
    GeneratorPrompt = apps.get_model("core", "GeneratorPrompt")
    GeneratorPrompt.objects.filter(code="semantic_phrases_from_cluster").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0122_update_semantic_clusters_prompt_source_books"),
    ]

    operations = [
        migrations.RunPython(add_semantic_phrases_prompt, reverse_code=remove_semantic_phrases_prompt),
    ]
