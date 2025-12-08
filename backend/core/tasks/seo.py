from celery import shared_task
import logging
from typing import Dict

from ..models import Topic, SEOKeywordSet, Client
from ..ai_generator import AIContentGenerator

logger = logging.getLogger(__name__)


def _get_latest_seo_keywords_for_client(client: Client) -> Dict[str, list]:
    """Возвращает свежие SEO списки по группам для клиента."""
    latest: Dict[str, list] = {}
    completed_sets = SEOKeywordSet.objects.filter(
        client=client,
        status='completed'
    ).order_by('-created_at')

    for seo_set in completed_sets:
        if seo_set.group_type:
            if seo_set.group_type not in latest and seo_set.keywords_list:
                latest[seo_set.group_type] = seo_set.keywords_list
                continue

        if seo_set.keyword_groups:
            for group_name, keywords in seo_set.keyword_groups.items():
                if group_name not in latest and isinstance(keywords, list) and keywords:
                    latest[group_name] = keywords

        if len(latest) >= len(SEOKeywordSet.GROUP_TYPE_CHOICES):
            break

    return latest


def _create_seo_records_for_generation(client: Client) -> Dict[str, SEOKeywordSet]:
    """
    Создать (или пересоздать) SEOKeywordSet записи для каждой группы перед генерацией.
    """
    SEOKeywordSet.objects.filter(
        client=client,
        status__in=['pending', 'generating']
    ).update(status='failed', error_log='Superseded by new SEO generation')

    records = {}
    for group_type, _ in SEOKeywordSet.GROUP_TYPE_CHOICES:
        records[group_type] = SEOKeywordSet.objects.create(
            client=client,
            status='generating',
            group_type=group_type
        )
    return records


def _collect_client_topics_and_keywords(client: Client):
    topics = Topic.objects.filter(client=client).order_by('name')
    topic_names = []
    raw_keywords = []

    for topic in topics:
        if topic.name:
            topic_names.append(topic.name)
        if topic.keywords:
            for kw in topic.keywords:
                if isinstance(kw, str):
                    trimmed = kw.strip()
                    if trimmed:
                        raw_keywords.append(trimmed)

    seen = set()
    deduped_keywords = []
    for kw in raw_keywords:
        if kw not in seen:
            deduped_keywords.append(kw)
            seen.add(kw)

    if not deduped_keywords and topic_names:
        deduped_keywords = topic_names.copy()

    return topic_names, deduped_keywords


def _generate_seo_keywords_for_client_instance(client: Client, language: str = "ru"):
    logger.info(f"Генерация SEO-фраз для клиента: {client.name}")

    seo_records = _create_seo_records_for_generation(client)

    try:
        generator = AIContentGenerator()
    except ValueError as e:
        logger.error(f"Ошибка инициализации AI генератора: {e}")
        logger.error("Убедитесь, что OPENROUTER_API_KEY установлен в переменных окружения")
        for record in seo_records.values():
            record.status = 'failed'
            record.error_log = f"AI initialization error: {str(e)}"
            record.save()
        return None

    topic_names, keywords_list = _collect_client_topics_and_keywords(client)
    topic_context = ", ".join(topic_names) if topic_names else client.name
    prompt_text = (
        f"Client: {client.name}, Topics: {topic_names or '[]'}, "
        f"Keywords: {keywords_list or '[]'}, Language: {language}"
    )

    def mark_record_success(group_type: str, keywords: list):
        record = seo_records.get(group_type)
        if not record:
            return
        record.keywords_list = keywords
        record.keyword_groups = {group_type: keywords}
        record.status = 'completed'
        record.error_log = ""
        record.prompt_used = prompt_text
        record.ai_model = generator.model
        record.topic = None
        record.save()

    result = generator.generate_seo_keywords(
        topic_name=topic_context,
        keywords=keywords_list,
        language=language,
        brand=client.name,
        avatar=client.avatar or "",
        pains=client.pains or "",
        desires=client.desires or "",
        objections=client.objections or "",
        on_group_generated=lambda group, data: mark_record_success(group, data)
    )

    if not result.get('success'):
        error_message = result.get('error', 'Unknown error')
        logger.error(f"Ошибка генерации SEO-фраз: {error_message}")
        for record in seo_records.values():
            if record.status == 'completed':
                continue
            record.status = 'failed'
            record.error_log = error_message
            record.prompt_used = prompt_text
            record.ai_model = generator.model
            record.keywords_list = []
            record.keyword_groups = {}
            record.save()
        return None

    keyword_groups = result.get('keyword_groups', {})

    completed_ids = []
    for group_type, record in seo_records.items():
        if record.status == 'completed':
            completed_ids.append(record.id)
            continue

        keywords = keyword_groups.get(group_type, [])
        if keywords:
            mark_record_success(group_type, keywords)
            completed_ids.append(seo_records[group_type].id)
        else:
            record.status = 'failed'
            record.error_log = f"Group '{group_type}' not returned by AI"
            record.prompt_used = prompt_text
            record.ai_model = generator.model
            record.keywords_list = []
            record.keyword_groups = {}
            record.save()

    logger.info(
        f"Успешно сгенерированы SEO-фразы для клиента '{client.name}' "
        f"(группы: {list(keyword_groups.keys())})"
    )

    total_keywords = sum(len(keywords or []) for keywords in keyword_groups.values())
    logger.info(f"Всего ключей: {total_keywords}")

    return completed_ids


@shared_task
def generate_seo_keywords_for_client(client_id: int, language: str = "ru"):
    """
    Сгенерировать SEO-подборку ключевых фраз для клиента используя AI.
    """
    try:
        client = Client.objects.get(id=client_id)
    except Client.DoesNotExist:
        logger.error(f"Клиент с ID {client_id} не найден")
        return None
    except Exception as exc:
        logger.error(f"Ошибка при получении клиента {client_id}: {exc}", exc_info=True)
        return None

    try:
        return _generate_seo_keywords_for_client_instance(client, language)
    except Exception as exc:
        logger.error(f"Ошибка при генерации SEO для клиента {client_id}: {exc}", exc_info=True)
        try:
            seo_sets = SEOKeywordSet.objects.filter(client_id=client_id, status='generating')
            for seo_set in seo_sets:
                seo_set.status = 'failed'
                seo_set.error_log = str(exc)
                seo_set.save()
        except Exception:
            pass
        return None


@shared_task
def generate_seo_keywords_for_topic(topic_id: int, language: str = "ru"):
    """
    [DEPRECATED] Сгенерировать SEO для клиента темы.
    Оставлено для обратной совместимости.
    """
    try:
        topic = Topic.objects.select_related('client').get(id=topic_id)
    except Topic.DoesNotExist:
        logger.error(f"Тема с ID {topic_id} не найдена")
        return None
    except Exception as exc:
        logger.error(f"Ошибка при получении темы {topic_id}: {exc}", exc_info=True)
        return None

    logger.info(
        f"generate_seo_keywords_for_topic вызван для темы '{topic.name}', переадресация на клиента '{topic.client.name}'"
    )
    return _generate_seo_keywords_for_client_instance(topic.client, language)
