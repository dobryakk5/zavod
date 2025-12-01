from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import Post, Schedule, SocialAccount
from .tasks import generate_image_for_post, generate_video_from_image, publish_schedule, regenerate_post_text
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
        model: Модель для генерации ('pollinations', 'nanobanana', 'huggingface' или 'flux2')

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
    model = request.GET.get('model', 'pollinations')

    # Валидация модели
    if model not in ['pollinations', 'nanobanana', 'huggingface', 'flux2']:
        return JsonResponse({
            'success': False,
            'error': f'Неизвестная модель: {model}'
        }, status=400)

    # Запустить задачу генерации изображения в Celery
    generate_image_for_post.delay(post_id, model=model)

    model_name_map = {
        'pollinations': 'Pollinations AI',
        'nanobanana': 'NanoBanana (Gemini 2.5 Flash)',
        'huggingface': 'HuggingFace (FLUX.1-dev)',
        'flux2': 'FLUX.2 (HuggingFace Space)'
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

    if not post.image:
        return JsonResponse({
            'success': False,
            'error': 'Сначала добавьте изображение к посту'
        }, status=400)

    generate_video_from_image.delay(post_id)

    return JsonResponse({
        'success': True,
        'message': 'Генерация видео запущена. Обновите страницу чуть позже.',
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
