from django.db import migrations


def add_wordstat_normalize_phrases_prompt(apps, schema_editor):
    GeneratorPrompt = apps.get_model("core", "GeneratorPrompt")
    GeneratorPrompt.objects.update_or_create(
        code="seo_wordstat_normalize_phrases",
        defaults={
            "group": "wordstat",
            "comment": "backend/core/ai_generator_seo.py: normalize_wordstat_phrases_ai",
            "prompt": """
$language_note
Ты опытный SEO-аналитик, который много лет работает с Яндекс Wordstat.

Твоя задача:
Привести пользовательские и интентные фразы
к БАЗОВЫМ Wordstat-формам,
по которым реально существует частотность.

Входные данные:
Список фраз, сгенерированных ИИ.
Фразы могут быть длинными, хвостатыми,
с уточнениями, предлогами, платформами,
или описывать конкретный сценарий использования.

Список фраз ($phrases_count):
$phrases_json

Задача:
Для КАЖДОЙ фразы определить её
СЕМАНТИЧЕСКИЙ ЦЕНТР
и выдать нормализованную форму,
подходящую для запроса в Wordstat.

Правила нормализации:

1. Это НЕ механическое обрезание.
   Нужно сохранить:
   - главный объект
   - главное действие
   - основной интент

2. Убирай:
   - предлоги
   - служебные слова
   - уточняющие хвосты (платформы, «онлайн», «с помощью»),
   ЕСЛИ они не формируют отдельный интент.

3. Оставляй:
   - устойчивые словосочетания
   - термины, которые пользователи реально вводят
   - формулировки, по которым вероятна частотность

4. Если фраза слишком узкая
   и в Wordstat по ней нет частотности:
   - укрупни её до ближайшего логического ядра

5. Если фраза содержит несколько смыслов —
   выбери ДОМИНИРУЮЩИЙ интент.

6. НЕ превращай все фразы
   в 1–2 сверхобщих слова.
   Избегай мусора вида:
   - "ai"
   - "контент"
   - "маркетинг"

7. Нормализованная форма должна:
   - выглядеть естественно для Wordstat
   - быть пригодной для оценки частотности
   - соответствовать исходному интенту

Формат ответа:

Для каждой фразы выведи:

- raw_phrase:
    исходная фраза

- normalized_phrase:
    форма для Wordstat

- comment:
    краткое объяснение,
    почему выбрана именно эта форма

Дополнительно:

1. Если несколько raw-фраз
   сводятся к одной normalized_phrase —
   это нормально.

2. Если фраза принципиально
   не имеет Wordstat-аналога —
   укажи:
   normalized_phrase = null
   и объясни почему.

Перед финальным ответом:

1. Проверь:
   - нет ли слишком общих нормализаций
   - нет ли потери интента
   - нет ли разных normalized_phrase
     для одного и того же смысла

2. Исправь, если нужно.

ФОРМАТ ОТВЕТА, СТРОГО JSON:
{
  "phrases": [
    {
      "raw_phrase": "исходная фраза",
      "normalized_phrase": "форма для Wordstat или null",
      "comment": "пояснение"
    }
  ]
}

Верни только JSON, без пояснений.
""",
        },
    )


def remove_wordstat_normalize_phrases_prompt(apps, schema_editor):
    GeneratorPrompt = apps.get_model("core", "GeneratorPrompt")
    GeneratorPrompt.objects.filter(code="seo_wordstat_normalize_phrases").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0124_semantic_lsi_prompt"),
    ]

    operations = [
        migrations.RunPython(
            add_wordstat_normalize_phrases_prompt,
            reverse_code=remove_wordstat_normalize_phrases_prompt,
        ),
    ]
