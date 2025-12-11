from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import Post, Schedule, SocialAccount, Client
from .tasks import generate_image_for_post, generate_video_from_image, publish_schedule, regenerate_post_text, analyze_telegram_channel_task
import json


@staff_member_required
@require_POST
def generate_post_image(request, post_id):
    """
    View для генерации изображения для поста через AJAX запрос из Django admin.

    Args:
        request: HTTP запрос
        post_id: ID поста

    Query parameters:
        model: Модель для генерации ('pollinations', 'nanobanana', 'huggingface', 'flux2' или 'sora_images')

    Returns:
        JsonResponse с результатом генерации
    """
    post = get_object_or_404(Post, id=post_id)

    # Проверить, что у поста есть текст
    if not post.text:
        return JsonResponse({
            'success': False,
            'error': 'Пост должен иметь текст для генерации изображения'
        }, status=400)

    # Получить модель из параметров запроса (по умолчанию pollinations)
    model_param = request.GET.get('model', 'pollinations')
    alias_map = {
        'telegram_bot': 'sora_images',
    }
    model = alias_map.get(model_param, model_param)

    # Валидация модели
    allowed_models = ['pollinations', 'nanobanana', 'huggingface', 'flux2', 'sora_images']
    if model not in allowed_models:
        return JsonResponse({
            'success': False,
            'error': f'Неизвестная модель: {model_param}'
        }, status=400)

    # Запустить задачу генерации изображения в Celery
    generate_image_for_post.delay(post_id, model=model)

    model_name_map = {
        'pollinations': 'Pollinations AI',
        'nanobanana': 'NanoBanana (Gemini 2.5 Flash)',
        'huggingface': 'HuggingFace (FLUX.1-dev)',
        'flux2': 'FLUX.2 (HuggingFace Space)',
        'sora_images': 'SORA Images (Telegram Bot)',
    }
    model_name = model_name_map.get(model, model)

    return JsonResponse({
        'success': True,
        'message': f'Генерация изображения запущена ({model_name}). Обновите страницу через несколько секунд.',
        'model': model
    })


@staff_member_required
@require_POST
def generate_post_video(request, post_id):
    """
    View для генерации видео из изображения поста.
    """
    post = get_object_or_404(Post, id=post_id)

    payload = {}
    if request.body:
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            payload = {}

    method = (payload.get('method') or request.GET.get('method') or 'wan').lower()
    source = (payload.get('source') or request.GET.get('source') or 'image').lower()

    allowed_methods = {'wan', 'veo'}
    allowed_sources = {'image', 'text'}

    if method not in allowed_methods:
        return JsonResponse({
            'success': False,
            'error': f'Неизвестный метод генерации видео: {method}'
        }, status=400)

    if source not in allowed_sources:
        return JsonResponse({
            'success': False,
            'error': f'Неизвестный тип источника: {source}'
        }, status=400)

    if source == 'image' and not post.images.exists():
        return JsonResponse({
            'success': False,
            'error': 'Сначала добавьте изображение к посту'
        }, status=400)

    if source == 'text' and not post.text:
        return JsonResponse({
            'success': False,
            'error': 'Для генерации по тексту нужен текст поста'
        }, status=400)

    if source == 'text' and method != 'veo':
        return JsonResponse({
            'success': False,
            'error': 'Текстовая генерация пока поддерживается только VEO'
        }, status=400)

    generate_video_from_image.delay(post_id, method=method, source=source)

    return JsonResponse({
        'success': True,
        'message': f'Генерация видео ({method}/{source}) запущена. Обновите страницу чуть позже.',
    })


@staff_member_required
@require_POST
def publish_schedule_now(request, schedule_id):
    """
    View для немедленной публикации Schedule через AJAX запрос из Django admin.

    Args:
        request: HTTP запрос
        schedule_id: ID расписания

    Returns:
        JsonResponse с результатом
    """
    schedule = get_object_or_404(Schedule, id=schedule_id)

    # Проверить статус
    if schedule.status != 'pending':
        return JsonResponse({
            'success': False,
            'error': f'Невозможно опубликовать: статус "{schedule.get_status_display()}"'
        }, status=400)

    # Обновить время на "сейчас"
    schedule.scheduled_at = timezone.now()
    schedule.save()

    # Запустить публикацию
    publish_schedule.delay(schedule_id)

    return JsonResponse({
        'success': True,
        'message': 'Публикация запущена. Страница будет перезагружена...'
    })


@staff_member_required
@require_POST
def quick_publish_post(request, post_id):
    """
    View для быстрой публикации поста в Telegram канал без создания расписания.

    Args:
        request: HTTP запрос с JSON телом содержащим social_account_id
        post_id: ID поста

    Returns:
        JsonResponse с результатом
    """
    post = get_object_or_404(Post, id=post_id)

    # Получаем social_account_id из JSON body
    try:
        body = json.loads(request.body)
        social_account_id = body.get('social_account_id')
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Неверный формат запроса'
        }, status=400)

    if not social_account_id:
        return JsonResponse({
            'success': False,
            'error': 'Не указан канал для публикации'
        }, status=400)

    # Получаем SocialAccount
    social_account = get_object_or_404(SocialAccount, id=social_account_id)

    # Проверяем, что SocialAccount принадлежит тому же клиенту
    if social_account.client != post.client:
        return JsonResponse({
            'success': False,
            'error': 'Канал не принадлежит клиенту поста'
        }, status=403)

    # Создаем Schedule со временем "сейчас"
    schedule = Schedule.objects.create(
        client=post.client,
        post=post,
        social_account=social_account,
        scheduled_at=timezone.now(),
        status='pending'
    )

    # Запускаем публикацию немедленно
    publish_schedule.delay(schedule.id)

    return JsonResponse({
        'success': True,
        'message': f'Публикация в "{social_account.name}" запущена. Страница будет перезагружена...'
    })


@staff_member_required
@require_POST
def regenerate_text(request, post_id):
    """
    View для регенерации текста поста через AJAX запрос из Django admin.

    Args:
        request: HTTP запрос
        post_id: ID поста

    Returns:
        JsonResponse с результатом регенерации
    """
    post = get_object_or_404(Post, id=post_id)

    # Запустить задачу регенерации текста в Celery
    regenerate_post_text.delay(post_id)

    return JsonResponse({
        'success': True,
        'message': 'Регенерация текста запущена. Страница будет перезагружена...'
    })


@staff_member_required
@require_POST
def analyze_telegram_channel(request, client_id):
    """
    View для анализа Telegram канала и автоматического заполнения профиля аудитории.

    Получает последние 20 постов из Telegram канала клиента,
    анализирует их с помощью AI и заполняет поля:
    - Аватар клиента (avatar)
    - Боли (pains)
    - Хотелки (desires)
    - Возражения/страхи (objections)

    Args:
        request: HTTP запрос
        client_id: ID клиента

    Returns:
        JsonResponse с результатом анализа
    """
    from django.conf import settings

    client = get_object_or_404(Client, id=client_id)

    # Проверка наличия канала
    if not client.telegram_client_channel:
        return JsonResponse({
            'success': False,
            'error': 'Не указан Telegram канал клиента'
        }, status=400)

    # Проверка наличия API credentials (клиентских или системных)
    api_id = client.telegram_api_id or settings.TELEGRAM_API_ID
    api_hash = client.telegram_api_hash or settings.TELEGRAM_API_HASH

    if not api_id or not api_hash:
        return JsonResponse({
            'success': False,
            'error': 'Не указаны Telegram API ID и API Hash. Настройте системные credentials в .env или укажите для клиента.'
        }, status=400)

    # Запустить задачу анализа канала в Celery
    analyze_telegram_channel_task.delay(client_id)

    return JsonResponse({
        'success': True,
        'message': 'Анализ канала запущен. Это может занять 1-2 минуты. Страница будет перезагружена...'
    })
