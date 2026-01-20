from django.db import migrations, models


PROMPTS = [
    {
        "code": "repair_json_structure",
        "comment": "backend/core/ai_generator_content.py: ContentGenerationMixin._repair_json_structure",
        "prompt": """
Ты получил ответ модели, который не соответствует ожидаемому JSON-формату.
Приведи текст ниже к строго валидному JSON согласно схеме:
$schema_hint

ВАЖНО:
- Верни только JSON без комментариев.
- Сохрани исходный смысл и данные.

Текст для исправления:
<<<$broken_text>>>
""",
    },
    {
        "code": "hook_title_ru",
        "comment": "backend/core/ai_generator_content.py: ContentGenerationMixin.generate_hook_title (ru)",
        "prompt": """
Создай короткий цепляющий заголовок (максимум 3 слова) для поста в соцсетях.

Тема: $topic_name
Тренд: $trend_title
Описание тренда: $trend_description

Стиль: $tone_ru
Тип поста: $type_description
Целевая аудитория: $avatar

Требования к заголовку:
- Максимум 3 слова на русском языке
- Должен быть коротким и привлекательным
- Вызывать интерес или эмоции
- Использовать восклицательные знаки, вопросы или прямое обращение
- Быть релевантным теме

Примеры цепляющих заголовков:
• "Это работает!"
• "Секрет успеха!"
• "Внимание!"
• "Почему именно?"
• "Узнайте сейчас!"

Создай только заголовок из 1-3 слов, без кавычек и дополнительного текста.

$seo_keyword_line
""",
    },
    {
        "code": "hook_title_en",
        "comment": "backend/core/ai_generator_content.py: ContentGenerationMixin.generate_hook_title (en)",
        "prompt": """
Create a short catchy hook title (5-10 words) for a social media post.

Topic: $topic_name
Trend: $trend_title
Trend description: $trend_description

Style: $tone
Post type: $type_description
Target audience: $avatar

Title requirements:
- Must be short and attractive
- Should provoke interest or emotions
- Use exclamation marks, questions, or direct address
- Maximum 10 words
- Be relevant to the topic

Examples of catchy titles:
• "This will change your life!"
• "The secret few people know"
• "Breaking: Important news!"
• "Why this works?"
• "Learn the truth right now!"

Create only the title, without quotes or additional text.

$seo_keyword_line
""",
    },
    {
        "code": "hook_title_seo_keyword_line",
        "comment": "backend/core/ai_generator_content.py: ContentGenerationMixin.generate_hook_title (seo keyword line)",
        "prompt": "SEO keyword to include: $first_keyword",
    },
    {
        "code": "post_text_seo_base",
        "comment": "backend/core/ai_generator_content.py: ContentGenerationMixin.generate_post_text (fallback seo)",
        "prompt": """
Ты - SEO-копирайтер и SMM-стратег, который создаёт контент для социальных сетей.

ДАННЫЕ О ЦЕЛЕВОЙ АУДИТОРИИ:
Аватар: $avatar
Боли: $pains
Хотелки: $desires
Возражения: $objections

ЗАДАЧА: Создай пост (≈$length_ru) для социальных сетей в $tone_ru стиле на $lang_name языке,
используя SEO-ключевые фразы: $seo_keywords_for_prompt.

ТЕМА БИЗНЕСА: $topic_name

ИНСТРУКЦИИ:
1. Сформируй цепляющий заголовок (до 100 символов)
2. Напиши основной текст, который:
   - Связывает SEO-ключи с продуктом/услугой
   - Отражает боли и желания целевой аудитории
   - Выстраивает логичную структуру для $post_type типа контента
   - Соответствует требуемой длине: $length_ru

$hashtags_block
$seo_block
$wordstat_block
$additional_block
$response_format_block
""",
    },
    {
        "code": "post_text_trend_base",
        "comment": "backend/core/ai_generator_content.py: ContentGenerationMixin.generate_post_text (fallback trend)",
        "prompt": """
Ты - опытный SMM-менеджер, который создаёт контент для социальных сетей.

ДАННЫЕ О ЦЕЛЕВОЙ АУДИТОРИИ:
Аватар: $avatar
Боли: $pains
Хотелки: $desires
Возражения: $objections

ЗАДАЧА: Создай пост (≈$length_ru) для социальных сетей в $tone_ru стиле на $lang_name языке.

ТЕМА БИЗНЕСА: $topic_name

НОВОСТЬ/ТРЕНД:
Заголовок: $trend_title
Описание: $trend_description
Источник: $trend_url

ИНСТРУКЦИИ:
1. Создай привлекательный заголовок поста (до 100 символов)
2. Напиши основной текст, который:
   - Объясняет суть новости/тренда
   - Показывает, почему это важно для аудитории именно с учётом его болей, хотелок и возражений
   - Связан с темой бизнеса "$topic_name"
   - Имеет $tone_ru тон
   - Соответствует требуемой длине: $length_ru

$hashtags_block
$seo_block
$wordstat_block
$additional_block
$response_format_block
""",
    },
    {
        "code": "post_text_hashtags_block",
        "comment": "backend/core/ai_generator_content.py: ContentGenerationMixin.generate_post_text (hashtags block)",
        "prompt": "3. Добавь $max_hashtags релевантных хэштега",
    },
    {
        "code": "post_text_seo_block",
        "comment": "backend/core/ai_generator_content.py: ContentGenerationMixin.generate_post_text (seo block)",
        "prompt": """
ВАЖНО - SEO ОПТИМИЗАЦИЯ:
Естественным образом включи в текст поста следующие SEO-ключевые фразы (по одной из каждой группы):
   - $seo_keywords_str

Фразы должны выглядеть органично и не выделяться из контекста.
""",
    },
    {
        "code": "post_text_wordstat_block",
        "comment": "backend/core/ai_generator_content.py: ContentGenerationMixin.generate_post_text (wordstat block)",
        "prompt": """
WORDSTAT-ФРАЗЫ:
Естественно включи 1-2 из фраз: $wordstat_phrases.
Не превращай текст в список ключей и не повторяй одну фразу много раз.
""",
    },
    {
        "code": "post_text_additional_block",
        "comment": "backend/core/ai_generator_content.py: ContentGenerationMixin.generate_post_text (additional block)",
        "prompt": """
ДОПОЛНИТЕЛЬНЫЕ ТРЕБОВАНИЯ:
$additional_instructions
""",
    },
    {
        "code": "post_text_response_format_block",
        "comment": "backend/core/ai_generator_content.py: ContentGenerationMixin.generate_post_text (response format)",
        "prompt": """
ФОРМАТ ОТВЕТА (строго JSON):
{
    "title": "Заголовок поста",
    "text": "Основной текст поста",
    "hashtags": ["хэштег1", "хэштег2", "хэштег3"]
}

Ответь ТОЛЬКО JSON, без дополнительных комментариев.
""",
    },
    {
        "code": "refine_text_wordstat",
        "comment": "backend/core/ai_generator_content.py: ContentGenerationMixin.refine_text_with_wordstat",
        "prompt": """
Ты редактор SMM-контента. Нужно оставить смысл поста и аккуратно вписать точные фразы из списка.

ЯЗЫК: $language
ФРАЗЫ: $phrases

ТЕКУЩИЙ ЗАГОЛОВОК:
$title

ТЕКУЩИЙ ТЕКСТ:
$text_for_prompt

ТРЕБОВАНИЯ:
- Сохрани длину текста ±15% и общий стиль.
- Добавь все указанные фразы один раз в естественных предложениях.
- Не превращай текст в набор ключей и не меняй тональность.

Формат ответа строго JSON:
{
  "title": "Обновленный заголовок (можно оставить без изменений)",
  "text": "Текст с встроенными фразами"
}
""",
    },
    {
        "code": "seo_keywords_pains",
        "comment": "backend/core/ai_generator_content.py: ContentGenerationMixin.generate_seo_keywords (pains)",
        "prompt": """
Ты — стратег по контенту и SEO-аналитике бренда $brand_name.
Тема бизнеса: $topic_name.
Проанализируй следующую аудиторию:

Аватар: $avatar_desc
Боли: $pains_desc
Возражения: $objections_desc
Хотелки: $desires_desc

Задача:
Сформируй список из 15–25 SEO-поисковых болей — фраз, которые люди реально могут вводить в Google/Yandex, пытаясь решить свои проблемы.
Формулируй так, как пишет сам клиент, максимально приближенно к естественному поисковому запросу.
Создавай запросы на $lang_name языке.

Выведи результат в формате Python-переменной:
seo_pains = [ ... ]
""",
    },
    {
        "code": "seo_keywords_desires",
        "comment": "backend/core/ai_generator_content.py: ContentGenerationMixin.generate_seo_keywords (desires)",
        "prompt": """
Ты — SEO-стратег бренда $brand_name.
Тема бизнеса: $topic_name.
На основе данных о целевой аудитории:

Аватар: $avatar_desc
Хотелки: $desires_desc
Боли: $pains_desc

Создай список из 15–25 желаний, которые люди ищут в поиске (ключевые запросы, связанные с ростом, мечтами, результатами) на $lang_name языке.

Выведи результат в формате Python-переменной:
seo_desires = [ ... ]
""",
    },
    {
        "code": "seo_keywords_objections",
        "comment": "backend/core/ai_generator_content.py: ContentGenerationMixin.generate_seo_keywords (objections)",
        "prompt": """
Ты — маркетолог бренда $brand_name.
Тема бизнеса: $topic_name.
Используя данные:

Боли: $pains_desc
Возражения: $objections_desc
Страхи: $objections_desc

Сгенерируй список из 10–20 поисковых возражений — фраз, которые человек ищет, сомневаясь или опасаясь купить. Используй формулировки, которые звучат как реальные запросы на $lang_name языке.

Выведи в формате:
seo_objections = [ ... ]
""",
    },
    {
        "code": "seo_keywords_avatar",
        "comment": "backend/core/ai_generator_content.py: ContentGenerationMixin.generate_seo_keywords (avatar)",
        "prompt": """
Ты — SEO-аналитик бренда $brand_name.
Тема бизнеса: $topic_name.
Используя данные об аудитории (аватар, профессия, стиль мышления, боли, хотелки), сформируй 10–15 формулировок того, как человек может описывать себя в поиске.

Аватар: $avatar_desc
Боли: $pains_desc
Хотелки: $desires_desc
Возражения: $objections_desc

Пример: "психолог который хочет клиентов через Instagram".
Генерируй формулировки на $lang_name языке.

Выведи в формате:
seo_avatar = [ ... ]
""",
    },
    {
        "code": "seo_keywords_list",
        "comment": "backend/core/ai_generator_content.py: ContentGenerationMixin.generate_seo_keywords (keywords)",
        "prompt": """
Ты — специалист по SEO-структурам для бренда $brand_name.
Тема бизнеса: $topic_name.
Используя данные:

Аватар: $avatar_desc
Боли: $pains_desc
Хотелки: $desires_desc
Возражения: $objections_desc
Существующие ключевые слова: $keywords_str

Создай список из 20–40 SEO ключей (низкочастотных, среднечастотных и ключей-модификаторов), которые можно использовать для блога, соцсетей, лендинга, рилс и автогенерации контента.
Обязательно включай комбинации:
- [боль + решение]
- [хотелка + инструмент]
- [ниша + контент]
- [бренд + категория продукта]

Фразы должны быть записаны как реальные поисковые запросы на $lang_name языке.

Выведи в формате:
seo_keywords = [ ... ]
""",
    },
    {
        "code": "book_recommendations",
        "comment": "backend/core/ai_generator_content.py: ContentGenerationMixin.generate_book_recommendations",
        "prompt": """
Ты — эксперт по персонализированным подборкам книг для предпринимателей и экспертов.

БРЕНД/ПРОЕКТ: $brand_text
ОПИСАНИЕ АВАТАРА: $avatar_text
КЛЮЧЕВЫЕ БОЛИ: $pains_text
КЛЮЧЕВЫЕ ЖЕЛАНИЯ: $desires_text

Найди 10 книг (на русском или в переводе), которые помогут этой аудитории решить проблемы и достичь желаемого.

ТРЕБОВАНИЯ:
- Указывай точное название и автора книги.
- Добавь 1–2 предложения, почему книга пригодится именно этой аудитории.
- Ориентируйся на практические, прикладные и вдохновляющие издания.
- Пиши на $lang_name языке.

ФОРМАТ ОТВЕТА, СТРОГО JSON:
{
  "books": [
    {"title": "Название", "author": "Автор", "reason": "Почему книга полезна"},
    ...
  ]
}

Верни ровно 10 элементов. Никаких пояснений вне JSON.
""",
    },
    {
        "code": "product_requirements_prompt",
        "comment": "backend/core/ai_generator_content.py: ContentGenerationMixin.generate_client_product_from_type (requirements)",
        "prompt": """
Ты — опытный продуктолог и методолог.
Сначала сформируй ТРЕБОВАНИЯ (не результат) для генерации продукта данного типа.

ВХОДНЫЕ ДАННЫЕ
- Бренд: $brand_text
- Тип продукта: $type_name
- Ценность типа: $type_value
- Цель типа: $type_goal

ПОРТРЕТ И МОТИВАЦИЯ АУДИТОРИИ
- Портрет ЦА: $avatar_text
- Боли: $pains_text
- Желания: $desires_text
- Возражения: $objections_text

WORDSTAT (ИЗБРАННОЕ)
$favorites_text
$extra_context_block

ЗАДАЧА
Сгенерируй 9 требований: по одному требованию на каждый блок результата:
1) name (вместе с short_description),
2) packages,
3–9) 7 частей структуры: audience, transformation, metrics, method, lesson_format (формат взаимодействия), program_modules, packaging.

ТРЕБОВАНИЯ К ТРЕБОВАНИЯМ
- Пиши на $lang_name языке.
- Каждое требование — это чёткая инструкция для генерации соответствующего блока (что включить, что исключить, сколько элементов).
- Обязательный акцент на типе продукта: short_description должен начинаться с "$type_name:".
- Не выдумывай лишние блоки: только перечисленные 9.
- Wordstat использовать как источники формулировок/контекста: 5–12 фраз суммарно по продукту (не обязательно в каждом блоке).

ФОРМАТ ОТВЕТА: СТРОГО JSON по схеме:
$requirements_schema_hint
""",
    },
    {
        "code": "product_block_prompt",
        "comment": "backend/core/ai_generator_content.py: ContentGenerationMixin.generate_client_product_from_type (block)",
        "prompt": """
Ты — продуктолог.
Сгенерируй ТОЛЬКО один блок продукта: $requirement_key.

$common_context

ТРЕБОВАНИЕ ДЛЯ ЭТОГО БЛОКА
$requirement_text

ДОПОЛНИТЕЛЬНО
- Пиши на $lang_name языке.
- Верни список "phrases_used" (0–5 фраз), которые реально использовал(а) из Wordstat в этом блоке.

ФОРМАТ ОТВЕТА: СТРОГО валидный JSON по схеме:
$schema_hint
""",
    },
    {
        "code": "story_episodes_prompt",
        "comment": "backend/core/ai_generator_content.py: StoryGenerationMixin.generate_story_episodes",
        "prompt": """
Ты - профессиональный сценарист и SMM-специалист, который создаёт вовлекающие истории для социальных сетей.

ЗАДАЧА: Создай увлекательную историю (мини-сериал) из $episode_count эпизодов на $lang_name языке.

ТЕМА БИЗНЕСА: $topic_name

ОСНОВА ДЛЯ ИСТОРИИ:
Тренд: $trend_title
Описание: $trend_description

ЦЕЛЕВАЯ АУДИТОРИЯ:
Хотелки и желания: $client_desires

ИНСТРУКЦИИ:
1. Придумай общий заголовок истории (1 предложение, до 100 символов)
2. Создай $episode_count эпизодов, которые:
   - Вовлекают аудиторию через эмоциональную связь
   - Учитывают желания целевой аудитории ($client_desires)
   - Связаны с темой бизнеса "$topic_name"
   - Основаны на тренде "$trend_title"
   - Имеют развитие сюжета от эпизода к эпизоду
   - Держат интригу и мотивируют читать дальше
   - Каждый эпизод имеет заголовок (20-80 символов)

3. История должна быть:
   - Вовлекающей и эмоциональной
   - С человеческими персонажами (если уместно)
   - С развитием конфликта или интриги
   - Связана с желаниями аудитории

ПРИМЕРЫ ХОРОШИХ ИСТОРИЙ:
- "Маша на занятиях по танцам увидела Колю" → "Коля пригласил Машу потанцевать" → "На следующее занятие он не пришел" → "Он вернулся в новой рубашке" → "Они встретились глазами"
- "Анна решила изменить свою жизнь" → "Первое занятие было тяжелым" → "Через неделю она почувствовала изменения" → "Коллеги заметили перемены" → "Анна обрела уверенность"

ФОРМАТ ОТВЕТА (строго JSON):
{
    "title": "Общий заголовок истории",
    "episodes": [
        {"order": 1, "title": "Заголовок эпизода 1"},
        ...
        {"order": $episode_count, "title": "Заголовок эпизода $episode_count"}
    ]
}

Ответь ТОЛЬКО JSON, без дополнительных комментариев.
""",
    },
    {
        "code": "story_post_from_episode_prompt",
        "comment": "backend/core/ai_generator_content.py: StoryGenerationMixin.generate_post_from_episode",
        "prompt": """
Ты - профессиональный копирайтер для социальных сетей.

ЗАДАЧА: Создай пост (≈$length_ru) для социальных сетей в $tone_ru стиле на $lang_name языке.

КОНТЕКСТ ИСТОРИИ:
- Общий заголовок истории: $story_title
- Эпизод $episode_number из $total_episodes: $episode_title

ТЕМА БИЗНЕСА: $topic_name

ДАННЫЕ О ЦЕЛЕВОЙ АУДИТОРИИ:
Аватар: $avatar
Боли: $pains
Хотелки: $desires
Возражения: $objections

ИНСТРУКЦИИ:
1. Создай привлекательный заголовок поста (до 100 символов)
2. Напиши основной текст, который:
   - Развивает сюжет эпизода "$episode_title"
   - Связан с общей историей "$story_title"
   - Учитывает желания и боли аудитории
   - Связан с темой бизнеса "$topic_name"
   - Имеет $tone_ru тон
   - Соответствует длине: $length_ru
   - Создаёт эмоциональную связь с читателем
   - Если это не последний эпизод, создаёт интригу для продолжения
$episode_extra_line

$hashtags_block
$additional_block
$response_format_block
""",
    },
    {
        "code": "story_post_episode_first_line",
        "comment": "backend/core/ai_generator_content.py: StoryGenerationMixin.generate_post_from_episode (first line)",
        "prompt": "   - Это первый эпизод - заинтригуй читателя и представь главного героя",
    },
    {
        "code": "story_post_episode_last_line",
        "comment": "backend/core/ai_generator_content.py: StoryGenerationMixin.generate_post_from_episode (last line)",
        "prompt": "   - Это финальный эпизод - создай удовлетворяющую концовку",
    },
    {
        "code": "story_post_episode_middle_line",
        "comment": "backend/core/ai_generator_content.py: StoryGenerationMixin.generate_post_from_episode (middle line)",
        "prompt": "   - Это промежуточный эпизод - развивай сюжет и поддерживай интригу",
    },
    {
        "code": "image_prompt_base",
        "comment": "backend/core/ai_generator_media.py: MediaGenerationMixin.generate_image_prompt",
        "prompt": """
Ты - эксперт по созданию промптов для генерации изображений.

ЗАДАЧА: Создай детальный промпт на английском языке для генерации изображения к посту в социальных сетях.

ПОСТ:
Заголовок: $post_title
Текст: $post_text

ИНСТРУКЦИИ:
1. Промпт должен быть на английском языке
2. Опиши визуальную сцену, которая отражает суть поста
3. Включи стиль изображения (например, "professional photography", "modern digital art", "minimalist design")
4. Укажи освещение, цветовую гамму, композицию
5. Промпт должен быть 1-2 предложения, очень конкретный и визуальный
6. Избегай текста на изображении
7. Фокусируйся на визуальной метафоре или прямом представлении темы

$admin_instructions_block

ФОРМАТ ОТВЕТА: Только промпт на английском языке, без дополнительных комментариев.

Пример хорошего промпта:
"A professional, modern office space with a diverse team collaborating around a sleek conference table, warm natural lighting through large windows, minimalist contemporary design, corporate photography style, high quality, focused composition"
""",
    },
    {
        "code": "image_prompt_admin_block",
        "comment": "backend/core/ai_generator_media.py: MediaGenerationMixin.generate_image_prompt (admin block)",
        "prompt": """
Дополнительные пожелания от администратора (учти их в ответе):
$extra_photo_instructions
""",
    },
    {
        "code": "video_prompt_base_instructions",
        "comment": "backend/core/ai_generator_media.py: MediaGenerationMixin.generate_video_prompt (base instructions)",
        "prompt": """
Ты — режиссёр и сценарист коротких вертикальных видео TikTok/Reels. На входе у тебя текст поста.

1. Сделай вовлекающий, визуально насыщенный prompt на английском языке.
2. Описывай сцену, настроение, движения камеры, переходы, ключевые визуальные объекты.
3. Стиль — современный, динамичный, вдохновляющий. Максимум 3 предложения.
4. Не добавляй хештеги, кавычки и технические команды.
""",
    },
    {
        "code": "video_prompt_admin_block",
        "comment": "backend/core/ai_generator_media.py: MediaGenerationMixin.generate_video_prompt (admin block)",
        "prompt": """
Дополнительные пожелания от администратора (учти их в ответе):
$extra_video_instructions
""",
    },
    {
        "code": "video_prompt_main",
        "comment": "backend/core/ai_generator_media.py: MediaGenerationMixin.generate_video_prompt",
        "prompt": """
$base_instructions

$admin_instructions_block

Пост ($lang_name):
Заголовок: $post_title
Текст: $post_text

Выход: только английский prompt для генерации видео.
""",
    },
    {
        "code": "video_prompt_fallback",
        "comment": "backend/core/ai_generator_media.py: MediaGenerationMixin._build_fallback_video_prompt",
        "prompt": """
Create a vertical 9:16 short-form social media video with cinematic motion.
Base language of the provided script: $lang_label.
Title: $post_title.
Script idea: $snippet
""",
    },
    {
        "code": "seo_wordstat_seed_groups",
        "comment": "backend/core/ai_generator_seo.py: generate_wordstat_seed_groups",
        "prompt": """
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
""",
    },
    {
        "code": "seo_wordstat_cluster",
        "comment": "backend/core/ai_generator_seo.py: cluster_wordstat_phrases",
        "prompt": """
Ты SEO-специалист. Кластеризуй поисковые фразы по интенту пользователя.

Требования:
- $language_note
- Используй ТОЛЬКО фразы из списка ниже.
- Каждая фраза должна попасть ровно в один кластер ИЛИ в unclustered.
- Названия кластеров должны быть короткими и понятными (2–5 слов).
- Не используй искусственные имена вида "Кластер 1".
- Сохраняй исходные формулировки фраз без изменений.
$existing_rules_block

Список фраз ($phrases_count):
$phrases_json

$existing_clusters_block

Формат ответа: СТРОГО валидный JSON по схеме:
$schema_hint
""",
    },
    {
        "code": "seo_wordstat_cluster_existing_rules",
        "comment": "backend/core/ai_generator_seo.py: cluster_wordstat_phrases (existing rules)",
        "prompt": """
- Если фраза подходит под существующий кластер, используй его название ТОЧНО как в списке.
- Если ни один из существующих кластеров не подходит, создай новый.
""",
    },
    {
        "code": "seo_wordstat_cluster_existing_clusters",
        "comment": "backend/core/ai_generator_seo.py: cluster_wordstat_phrases (existing clusters)",
        "prompt": """
Существующие кластеры:
$existing_clusters_json
""",
    },
    {
        "code": "seo_text_analysis",
        "comment": "backend/core/ai_generator_seo.py: analyze_seo_text",
        "prompt": """
Ты SEO-редактор. Проанализируй текст и дай рекомендации по улучшению.

$language_note

Основной запрос: $main_query

Найденные ключи:
$found_payload

Отсутствующие ключи:
$missing_payload

Покрытие кластеров:
$clusters_payload

Текст (фрагмент):
<<<$truncated_text>>>

Верни строго JSON:
{
  "intent": "информационный|коммерческий|навигационный|смешанный",
  "strengths": ["..."],
  "gaps": ["..."],
  "recommendations": ["..."],
  "keyword_advice": {
    "include": ["..."],
    "exclude": ["..."],
    "separate_article": ["..."]
  },
  "rewrite_plan": {
    "h1": "...",
    "h2": ["..."],
    "h3": ["..."],
    "add_blocks": ["..."],
    "notes": ["..."]
  },
  "rewrite_text": "..."
}

$rewrite_note
""",
    },
    {
        "code": "seo_text_rewrite_note_on",
        "comment": "backend/core/ai_generator_seo.py: analyze_seo_text (rewrite on)",
        "prompt": "Заполни rewrite_plan и короткий rewrite_text (до 1500 символов).",
    },
    {
        "code": "seo_text_rewrite_note_off",
        "comment": "backend/core/ai_generator_seo.py: analyze_seo_text (rewrite off)",
        "prompt": "rewrite_plan оставь пустым, rewrite_text оставь пустым.",
    },
]


def create_generator_prompts(apps, schema_editor):
    GeneratorPrompt = apps.get_model("core", "GeneratorPrompt")
    for item in PROMPTS:
        prompt_text = (item.get("prompt") or "").strip()
        GeneratorPrompt.objects.update_or_create(
            code=item["code"],
            defaults={
                "prompt": prompt_text,
                "comment": item.get("comment", ""),
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0106_client_product_service"),
    ]

    operations = [
        migrations.CreateModel(
            name="GeneratorPrompt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.SlugField(max_length=120, unique=True)),
                ("prompt", models.TextField()),
                ("comment", models.TextField(blank=True, help_text="Где используется")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Промпт генератора",
                "verbose_name_plural": "Промпты",
                "ordering": ("code",),
            },
        ),
        migrations.RunPython(create_generator_prompts, reverse_code=migrations.RunPython.noop),
    ]
