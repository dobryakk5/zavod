from django.db import migrations


def add_semantic_lsi_prompt(apps, schema_editor):
    GeneratorPrompt = apps.get_model("core", "GeneratorPrompt")
    GeneratorPrompt.objects.update_or_create(
        code="semantic_lsi_from_cluster",
        defaults={
            "group": "seo",
            "comment": "backend/core/ai_generator_content.py: ContentGenerationMixin.generate_semantic_lsi_from_cluster",
            "prompt": """
$language_note
Ты специалист по LSI и тематическому SEO.

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

Задача:
Сгенерировать LSI-ФРАЗЫ
(контекстные, тематические, поддерживающие)
для данного кластера
для таблицы `phrases` (type = lsi).

Требования:

1. Это НЕ SEO-ключи.
   Это:
   - термины,
   - понятия,
   - темы,
   - сущности,
   - формулировки,
   которые усиливают релевантность
   страницы под основной интент.

2. Не включай:
   - прямые SEO-ключи,
   - коммерческие фразы,
   - фразы с другим интентом.

3. Учитывай:
   - терминологию из source_books,
   - стиль и лексику ниши.

4. Категории LSI, которые нужно покрыть:
   - термины и понятия
   - методы и процессы
   - инструменты и технологии
   - проблемы и ошибки
   - результаты и эффекты
   - сравнения и альтернативы
   - вопросы пользователей

5. Количество:
   - 30–100 фраз,
   - в зависимости от ширины интента.

Сделай:

Список LSI-фраз в формате,
пригодном для записи в БД.

Для каждой фразы:

- phrase:
    текст фразы

- type:
    lsi

- category:
    одна из:
    term / process / tool / problem / result / comparison / question

- comment:
    почему эта фраза усиливает
    релевантность этого кластера

Перед финальным ответом:

1. Проверь:
   - нет ли SEO-ключей среди LSI
   - нет ли дублей
   - не слишком ли узкий набор (меньше 20 фраз)
   - не слишком ли широкий набор (больше 150 фраз)

2. Если есть:
   - удали
   - объедини
   - сократи

ФОРМАТ ОТВЕТА, СТРОГО JSON:
{
  "phrases": [
    {
      "phrase": "текст фразы",
      "type": "lsi",
      "category": "term|process|tool|problem|result|comparison|question",
      "comment": "пояснение"
    }
  ]
}

Верни только JSON, без пояснений.
""",
        },
    )


def remove_semantic_lsi_prompt(apps, schema_editor):
    GeneratorPrompt = apps.get_model("core", "GeneratorPrompt")
    GeneratorPrompt.objects.filter(code="semantic_lsi_from_cluster").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0123_semantic_phrases_prompt"),
    ]

    operations = [
        migrations.RunPython(add_semantic_lsi_prompt, reverse_code=remove_semantic_lsi_prompt),
    ]
