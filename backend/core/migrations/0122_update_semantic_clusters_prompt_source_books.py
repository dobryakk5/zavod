from django.db import migrations


def update_semantic_clusters_prompt(apps, schema_editor):
    GeneratorPrompt = apps.get_model("core", "GeneratorPrompt")
    GeneratorPrompt.objects.update_or_create(
        code="semantic_clusters_from_group",
        defaults={
            "group": "seo",
            "comment": "backend/core/ai_generator_content.py: ContentGenerationMixin.generate_semantic_clusters_from_group",
            "prompt": """
$language_note
Ты SEO-стратег и аналитик интентов.

Тема проекта: $niche_text
Целевая аудитория: $audience_text
Описание продукта: $product_text

Смысловая группа:
- name: $group_name
- description: $group_description
- scope: $group_scope
- expected_clusters: $group_expected_clusters
- examples: $group_examples

Смысловая группа взята из книг: $group_source_books

Задача:
Сформировать SEO-КЛАСТЕРЫ (интенты)
внутри данной смысловой группы
для таблицы `clusters`.

Требования:

1. Кластер = 1 поисковый интент = 1 страница.

2. Делить по ЦЕЛИ пользователя,
   а не по:
   - формулировкам ключей
   - SEO-синонимам
   - типу страницы
   - типу запроса (инфо / коммерческий)

3. Не дроби один интент на несколько кластеров,
   если:
   - отличается только формулировка
   - отличается порядок слов
   - это синонимы

4. Делай отдельный кластер, если:
   - другая цель пользователя
   - другой ожидаемый результат
   - другой формат решения задачи
   - другой CTA

5. Количество кластеров должно:
   - быть близко к expected_clusters
   - соответствовать scope группы
   - не быть:
     - слишком мелким (1–2 фразы)
     - слишком широким (50+ фраз)

Сделай:

Список кластеров в формате,
пригодном для записи в БД.

Для каждого кластера:

- name:
    короткое человеческое название интента

- description:
    какую задачу решает пользователь
    и какой результат он ожидает

- main_keyword:
    основной SEO-ключ,
    который лучше всего выражает этот интент

- intent:
    info / commercial / navigational / brand

- user_goal:
    цель пользователя своими словами

- cta:
    что пользователь должен сделать на странице
    (прочитать, скачать, оставить заявку, купить, попробовать)

- priority:
    high / medium / low
    (оценка ценности этого кластера для бизнеса)

- examples:
    5–10 примеров фраз,
    которые должны входить в этот кластер

В конце:

1. Общее количество кластеров.

2. Краткий комментарий:
   - почему именно такое деление
   - нет ли слишком узких или слишком широких кластеров

Перед финальным ответом:

1. Проверь:
   - нет ли двух кластеров с одинаковым интентом
   - нет ли кластеров,
     отличающихся только формулировками

2. Если есть:
   - объедини
   - переименуй
   - скорректируй main_keyword

ФОРМАТ ОТВЕТА, СТРОГО JSON:
{
  "clusters": [
    {
      "name": "Название",
      "description": "Какую задачу решает пользователь",
      "main_keyword": "основной ключ",
      "intent": "info|commercial|navigational|brand",
      "user_goal": "цель пользователя",
      "cta": "что сделать",
      "priority": "high|medium|low",
      "examples": ["пример 1", "пример 2"]
    }
  ],
  "total_clusters": 12,
  "comment": "краткий комментарий"
}

Верни только JSON, без пояснений.
""",
        },
    )


def remove_semantic_clusters_prompt_update(apps, schema_editor):
    GeneratorPrompt = apps.get_model("core", "GeneratorPrompt")
    GeneratorPrompt.objects.filter(code="semantic_clusters_from_group").update(
        prompt="""
$language_note
Ты SEO-стратег и аналитик интентов.

Тема проекта: $niche_text
Целевая аудитория: $audience_text
Описание продукта: $product_text

Смысловая группа:
- name: $group_name
- description: $group_description
- scope: $group_scope
- expected_clusters: $group_expected_clusters
- examples: $group_examples

Задача:
Сформировать SEO-КЛАСТЕРЫ (интенты)
внутри данной смысловой группы
для таблицы `clusters`.

Требования:

1. Кластер = 1 поисковый интент = 1 страница.

2. Делить по ЦЕЛИ пользователя,
   а не по:
   - формулировкам ключей
   - SEO-синонимам
   - типу страницы
   - типу запроса (инфо / коммерческий)

3. Не дроби один интент на несколько кластеров,
   если:
   - отличается только формулировка
   - отличается порядок слов
   - это синонимы

4. Делай отдельный кластер, если:
   - другая цель пользователя
   - другой ожидаемый результат
   - другой формат решения задачи
   - другой CTA

5. Количество кластеров должно:
   - быть близко к expected_clusters
   - соответствовать scope группы
   - не быть:
     - слишком мелким (1–2 фразы)
     - слишком широким (50+ фраз)

Сделай:

Список кластеров в формате,
пригодном для записи в БД.

Для каждого кластера:

- name:
    короткое человеческое название интента

- description:
    какую задачу решает пользователь
    и какой результат он ожидает

- main_keyword:
    основной SEO-ключ,
    который лучше всего выражает этот интент

- intent:
    info / commercial / navigational / brand

- user_goal:
    цель пользователя своими словами

- cta:
    что пользователь должен сделать на странице
    (прочитать, скачать, оставить заявку, купить, попробовать)

- priority:
    high / medium / low
    (оценка ценности этого кластера для бизнеса)

- examples:
    5–10 примеров фраз,
    которые должны входить в этот кластер

В конце:

1. Общее количество кластеров.

2. Краткий комментарий:
   - почему именно такое деление
   - нет ли слишком узких или слишком широких кластеров

Перед финальным ответом:

1. Проверь:
   - нет ли двух кластеров с одинаковым интентом
   - нет ли кластеров,
     отличающихся только формулировками

2. Если есть:
   - объедини
   - переименуй
   - скорректируй main_keyword

ФОРМАТ ОТВЕТА, СТРОГО JSON:
{
  "clusters": [
    {
      "name": "Название",
      "description": "Какую задачу решает пользователь",
      "main_keyword": "основной ключ",
      "intent": "info|commercial|navigational|brand",
      "user_goal": "цель пользователя",
      "cta": "что сделать",
      "priority": "high|medium|low",
      "examples": ["пример 1", "пример 2"]
    }
  ],
  "total_clusters": 12,
  "comment": "краткий комментарий"
}

Верни только JSON, без пояснений.
""",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0121_update_semantic_groups_prompt_source_books"),
    ]

    operations = [
        migrations.RunPython(
            update_semantic_clusters_prompt,
            reverse_code=remove_semantic_clusters_prompt_update,
        ),
    ]
