import logging

from django.contrib import admin, messages
from django.contrib.admin import widgets as admin_widgets
from django import forms
from django.urls import reverse, path
from django.db import models
from django.http import HttpResponseRedirect
from django.middleware.csrf import get_token
from django.template.loader import render_to_string
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.core.exceptions import PermissionDenied

from .models import (
    Client,
    UserTenantRole,
    SocialAccount,
    Connection,
    PostJob,
    Post,
    PostImage,
    PostVideo,
    Schedule,
    Topic,
    TrendItem,
    ContentTemplate,
    SEOKeywordSet,
    Story,
    PostType,
    PostTone,
    SystemSetting,
    ProductType,
    Article,
    Articles,
    ArticleBlock,
)
from .system_settings import invalidate_system_settings_cache, get_image_generation_model, get_image_generation_method

logger = logging.getLogger(__name__)


def _file_url_if_exists(file_field):
    """
    Возвращает URL файла, только если он действительно существует на сторидже.
    Позволяет избежать 404 при клике на ссылку, когда физический файл удалён.
    """
    if not file_field:
        return None

    file_name = getattr(file_field, "name", "")
    if not file_name:
        return None

    storage = getattr(file_field, "storage", None)
    if not storage:
        return None

    try:
        if storage.exists(file_name):
            return file_field.url
    except Exception as exc:  # pragma: no cover - диагностика окружения
        logger.warning("Failed to access file %s: %s", file_name, exc)
    return None


class ContentTemplateInline(admin.TabularInline):
    model = ContentTemplate
    extra = 0
    fields = ("name", "tone", "length", "is_default")
    show_change_link = True


class ClientSEOKeywordSetInline(admin.TabularInline):
    model = SEOKeywordSet
    fk_name = "client"
    extra = 0
    fields = ("group_type", "status", "keywords_preview", "created_at")
    readonly_fields = ("group_type", "status", "keywords_preview", "created_at")
    show_change_link = True
    can_delete = False

    def keywords_preview(self, obj):
        if obj.keywords_list:
            return ", ".join(obj.keywords_list[:3]) + ("..." if len(obj.keywords_list) > 3 else "")
        if obj.keyword_groups:
            preview = []
            for group_name, items in obj.keyword_groups.items():
                if isinstance(items, list):
                    preview.extend(items[:2])
            if preview:
                return ", ".join(preview[:3]) + ("..." if len(preview) > 3 else "")
        return "-"
    keywords_preview.short_description = "Ключи"


class ArticleBlockInlineForm(forms.ModelForm):
    class Meta:
        model = ArticleBlock
        fields = "__all__"
        widgets = {
            "keywords": forms.Textarea(attrs={"rows": 2, "style": "width: 96%; font-family: monospace;"}),
            "key_points": forms.Textarea(attrs={"rows": 4, "style": "width: 96%;"}),
            "prompt_used": forms.Textarea(attrs={"rows": 10, "style": "width: 96%; font-family: monospace;"}),
            "content": forms.Textarea(attrs={"rows": 10, "style": "width: 96%;"}),
        }


class ArticleBlockInline(admin.StackedInline):
    model = ArticleBlock
    form = ArticleBlockInlineForm
    extra = 0
    can_delete = False
    ordering = ("order", "id")
    readonly_fields = ("block_key", "prompt_used", "regeneration_count", "created_at", "updated_at")
    fields = (
        ("order", "block_key", "status"),
        ("h2_title", "subquery"),
        "micro_intent",
        "key_points",
        "keywords",
        "prompt_used",
        "content",
        ("regeneration_count", "updated_at"),
    )


class ArticleBlockPromptTemplateAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "prompt_template" in self.fields:
            self.fields["prompt_template"].help_text = (
                "Доступные переменные: "
                "{{main_query}}, {{audience}}, {{context}}, {{h2_title}}, {{subquery}}, "
                "{{intent}}, {{key_points}}, {{wordstat2}}, {{keywords}}, {{product_context}}. "
                "Если данных для переменной нет — будет пусто."
            )

    class Meta:
        model = Articles
        fields = "__all__"
        widgets = {
            "prompt_template": forms.Textarea(attrs={"rows": 18, "style": "width: 96%; font-family: monospace;"}),
        }


@admin.register(Articles)
class ArticlePromptTemplatesAdmin(admin.ModelAdmin):
    list_display = ("block_key", "updated_at")
    search_fields = ("block_key", "prompt_template")
    ordering = ("block_key",)
    form = ArticleBlockPromptTemplateAdminForm
    readonly_fields = ("created_at", "updated_at")

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "wordstat", "status", "created_at", "updated_at")
    list_select_related = ("client", "created_by")
    list_filter = ("status", "client", "created_at", "updated_at")
    search_fields = ("wordstat", "tripwire_product_name", "lead_product_name")
    autocomplete_fields = ("client", "created_by")
    date_hierarchy = "created_at"
    inlines = (ArticleBlockInline,)
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Основное", {"fields": ("client", "wordstat", "status", "audience")}),
        ("Продукты", {"fields": ("tripwire_product_id", "tripwire_product_name", "lead_product_id", "lead_product_name")}),
        ("Контекст (чекбоксы)", {"fields": ("selected_why_now", "selected_solution")}),
        ("Опции (AI-ответы)", {"fields": ("options_why_now", "options_solution"), "classes": ("collapse",)}),
        ("Структура", {"fields": ("outline_markdown",)}),
        ("Результат", {"fields": ("result_html",), "classes": ("collapse",)}),
        ("Blueprint SEO блоков (JSON)", {"fields": ("seo_blocks",), "classes": ("collapse",)}),
        ("Система", {"fields": ("created_by", "created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "timezone", "has_business_info")
    search_fields = ("name", "slug", "avatar", "pains", "desires", "objections")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ContentTemplateInline, ClientSEOKeywordSetInline]
    actions = ["generate_seo_keywords_action"]
    readonly_fields = ("analyze_channel_button",)

    fieldsets = (
        ("Основная информация", {
            "fields": ("name", "brand_name", "slug", "timezone"),
        }),
        ("Описание целевой аудитории", {
            "fields": ("avatar", "pains", "desires", "objections"),
            "description": "Эта информация используется AI для генерации более персонализированного контента, который попадает в боли и желания вашей аудитории"
        }),
        ("Видео", {
            "fields": ("base_video_prompt", "add_video_prompt", "video_prompt"),
            "description": "Настройте инструкции для генерации видео именно для этого клиента. Используйте base_video_prompt для базовых инструкций AI и add_video_prompt для дополнительных пожеланий.",
            "classes": ("collapse",),
        }),
        ("Telegram", {
            "fields": ("telegram_client_channel", "analyze_channel_button", "telegram_api_id", "telegram_api_hash", "telegram_source_channels"),
            "classes": ("collapse",),
        }),
        ("RSS фиды", {
            "fields": ("rss_source_feeds",),
            "classes": ("collapse",),
        }),
        ("YouTube", {
            "fields": ("youtube_api_key", "youtube_source_channels"),
            "classes": ("collapse",),
        }),
        ("Instagram", {
            "fields": ("instagram_access_token", "instagram_source_accounts"),
            "classes": ("collapse",),
        }),
        ("VKontakte", {
            "fields": ("vkontakte_access_token", "vkontakte_source_groups"),
            "classes": ("collapse",),
        }),
    )

    def has_business_info(self, obj):
        """Индикатор заполненности информации о бизнесе"""
        filled_count = sum([
            bool(obj.avatar),
            bool(obj.pains),
            bool(obj.desires),
            bool(obj.objections)
        ])
        if filled_count == 4:
            return "✓ (4/4)"
        elif filled_count > 0:
            return f"~ ({filled_count}/4)"
        return "- (0/4)"
    has_business_info.short_description = "Профиль аудитории"

    def analyze_channel_button(self, obj):
        """Кнопка для анализа Telegram канала и заполнения профиля аудитории"""
        if not obj.pk:
            return "Сохраните клиента, чтобы использовать эту функцию"

        if not obj.telegram_client_channel:
            return format_html(
                '<div style="color: #dc3545;">⚠️ Сначала укажите канал клиента выше</div>'
            )

        analyze_url = reverse('core:analyze_telegram_channel', args=[obj.pk])

        return format_html(
            '''
            <div style="margin: 10px 0;">
                <button type="button" class="analyze-channel-btn"
                    onclick="analyzeChannel('{url}', this)"
                    style="padding: 10px 20px; background-color: #28a745; color: white;
                    border: none; border-radius: 4px; cursor: pointer; font-size: 14px; font-weight: bold;">
                    🔍 Получить базовую информацию из канала
                </button>
                <div id="analyze-status" style="margin-top: 10px; font-size: 13px;"></div>
                <div style="color: #6c757d; font-size: 12px; margin-top: 8px;">
                    Будут проанализированы последние 20 постов из канала <strong>{channel}</strong>
                    для автоматического заполнения полей "Аватар клиента", "Боли", "Хотелки" и "Возражения/страхи"
                </div>
            </div>
            <script>
            function getCookie(name) {{
                let cookieValue = null;
                if (document.cookie && document.cookie !== '') {{
                    const cookies = document.cookie.split(';');
                    for (let i = 0; i < cookies.length; i++) {{
                        const cookie = cookies[i].trim();
                        if (cookie.substring(0, name.length + 1) === (name + '=')) {{
                            cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                            break;
                        }}
                    }}
                }}
                return cookieValue;
            }}

            function analyzeChannel(url, button) {{
                const statusDiv = document.getElementById('analyze-status');
                const originalText = button.textContent;

                button.disabled = true;
                button.style.opacity = '0.6';
                button.textContent = '⏳ Анализирую канал...';
                statusDiv.innerHTML = '<span style="color: #007bff;">⏳ Получение постов из Telegram канала...</span>';

                fetch(url, {{
                    method: 'POST',
                    headers: {{
                        'X-CSRFToken': getCookie('csrftoken'),
                        'Content-Type': 'application/json',
                    }},
                    credentials: 'same-origin'
                }})
                .then(response => response.json().then(data => [response.ok, data]))
                .then(([ok, data]) => {{
                    if (!ok || !data.success) {{
                        throw new Error(data.error || 'Ошибка анализа канала');
                    }}
                    statusDiv.innerHTML = '<span style="color: #28a745;">✓ ' + data.message + '</span>';
                    setTimeout(() => window.location.reload(), 2000);
                }})
                .catch(error => {{
                    statusDiv.innerHTML = '<span style="color: #dc3545;">✗ ' + error.message + '</span>';
                    button.disabled = false;
                    button.style.opacity = '1';
                    button.textContent = originalText;
                }});
            }}
            </script>
            ''',
            url=analyze_url,
            channel=obj.telegram_client_channel
        )
    analyze_channel_button.short_description = "AI Анализ канала"

    def generate_seo_keywords_action(self, request, queryset):
        """Сгенерировать SEO подборку для выбранных клиентов"""
        from .tasks import generate_seo_keywords_for_client

        count = 0
        for client in queryset:
            generate_seo_keywords_for_client.delay(client.id)
            count += 1

        self.message_user(request, f"Запущена генерация SEO-фраз для {count} клиентов")
    generate_seo_keywords_action.short_description = "Сгенерировать SEO для клиентов"


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = (
        "default_ai_model",
        "post_ai_model",
        "fallback_ai_model",
        "image_generation_method",
        "image_openrouter_model",
        "image_generation_timeout",
        "video_generation_timeout",
        "updated_at",
    )
    fieldsets = (
        (
            "AI настройки",
            {
            "fields": (
                "default_ai_model",
                "post_ai_model",
                "fallback_ai_model",
                "image_generation_method",
                "image_openrouter_model",
                "video_prompt_instructions",
                "photo_prompt_instructions",
            )
            },
        ),
        ("Таймауты генерации", {"fields": ("image_generation_timeout", "video_generation_timeout")}),
        ("Служебное", {"fields": ("created_at", "updated_at")}),
    )
    readonly_fields = ("created_at", "updated_at")

    def has_add_permission(self, request):
        return not SystemSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        invalidate_system_settings_cache()


@admin.register(UserTenantRole)
class UserTenantRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "client", "role")
    list_filter = ("role", "client")
    search_fields = ("user__username", "user__email", "client__name")


class SocialAccountInline(admin.TabularInline):
    model = SocialAccount
    extra = 0


class ScheduleInline(admin.StackedInline):
    model = Schedule
    extra = 1
    form = None  # Будет установлена позже, после объявления ScheduleAdminForm
    fields = ("client_display", "telegram_channels", "social_account", "connection", "scheduled_at", "status", "publish_now_button")
    readonly_fields = ("client_display", "publish_now_button")

    classes = ('collapse',)  # Сворачивать по умолчанию для компактности

    def get_form(self, request, obj=None, **kwargs):
        """Передаём parent object (Post) в форму"""
        form = super().get_form(request, obj, **kwargs)

        # Сохраняем ссылку на Post в классе формы для доступа в __init__
        form.parent_post = obj

        return form

    def client_display(self, obj):
        """Отображение клиента (только для чтения)"""
        if obj and obj.client:
            return obj.client.name
        # Для новых записей получаем клиента из Post
        return "(определится автоматически)"
    client_display.short_description = "Клиент"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Фильтруем social_account только по Telegram каналам текущего клиента"""
        if db_field.name == "social_account":
            # Получаем Post из URL
            post_id = request.resolver_match.kwargs.get('object_id')
            if post_id:
                try:
                    post = Post.objects.get(pk=post_id)
                    kwargs["queryset"] = SocialAccount.objects.filter(
                        client=post.client,
                        platform='telegram'
                    )
                except Post.DoesNotExist:
                    pass

        if db_field.name == "client":
            # Получаем Post из URL и автоматически выбираем его клиента
            post_id = request.resolver_match.kwargs.get('object_id')
            if post_id:
                try:
                    post = Post.objects.get(pk=post_id)
                    kwargs["initial"] = post.client
                    kwargs["disabled"] = True
                except Post.DoesNotExist:
                    pass

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_formset(self, request, obj=None, **kwargs):
        """Автозаполнение клиента и поста для новых Schedule"""
        formset = super().get_formset(request, obj, **kwargs)

        # Сохраняем ссылку на obj (Post) в formset для доступа из формы
        formset.parent_post = obj

        # Если это страница редактирования Post
        if obj:
            # Переопределяем _construct_form для передачи parent_post в каждую форму
            original_construct_form = formset._construct_form

            def new_construct_form(self, i, **kwargs):
                form = original_construct_form(self, i, **kwargs)
                # Устанавливаем post для каждой формы через instance
                if not form.instance.pk:
                    form.instance.post = obj
                    form.instance.client = obj.client
                # Также устанавливаем на класс формы для доступа в __init__
                form.__class__.parent_post = obj
                return form

            formset._construct_form = new_construct_form

        return formset

    def save_formset(self, request, form, formset, change):
        """Переопределяем сохранение formset для обработки telegram_channels"""
        from django.utils import timezone
        from .tasks import publish_schedule

        # Сначала получаем parent Post
        post = form.instance

        # Собираем данные о telegram_channels до стандартного сохранения
        telegram_schedules_data = []

        for inline_form in formset.forms:
            if hasattr(inline_form, 'cleaned_data') and inline_form.cleaned_data:
                # Пропускаем удаленные и пустые формы
                if inline_form.cleaned_data.get('DELETE', False) or not inline_form.has_changed():
                    continue

                selected_channels = inline_form.cleaned_data.get('telegram_channels', [])

                # Если выбраны чекбоксы telegram_channels
                if selected_channels:
                    # Сохраняем данные для последующего создания
                    telegram_schedules_data.append({
                        'channels': selected_channels,
                        'scheduled_at': inline_form.cleaned_data.get('scheduled_at'),
                    })
                    # Помечаем форму как удаленную, чтобы не сохранять пустую запись
                    inline_form.cleaned_data['DELETE'] = True

        # Стандартное сохранение formset (для dropdown social_account)
        super().save_formset(request, form, formset, change)

        # Создаем Schedule для каждого выбранного telegram канала
        now = timezone.now()
        for schedule_data in telegram_schedules_data:
            for channel_id in schedule_data['channels']:
                try:
                    social_account = SocialAccount.objects.get(id=int(channel_id))
                    schedule = Schedule.objects.create(
                        client=post.client,
                        post=post,
                        social_account=social_account,
                        scheduled_at=schedule_data['scheduled_at'],
                        status='pending'
                    )

                    # Если время публикации в прошлом или сейчас, запускаем публикацию сразу
                    if schedule.scheduled_at <= now:
                        publish_schedule.delay(schedule.id)

                except (SocialAccount.DoesNotExist, ValueError):
                    pass

    def publish_now_button(self, obj):
        """Кнопка 'Опубликовать сейчас' для каждого Schedule"""
        if obj.pk and obj.status == 'pending':
            from django.urls import reverse
            publish_url = reverse('core:publish_schedule_now', args=[obj.pk])
            return format_html(
                '<a class="button" href="javascript:void(0)" '
                'onclick="if(confirm(\'Опубликовать сейчас?\')) {{ '
                'fetch(\'{}\', {{method: \'POST\', headers: {{\'X-CSRFToken\': document.querySelector(\'[name=csrfmiddlewaretoken]\').value}}}}) '
                '.then(response => response.json()) '
                '.then(data => {{ if(data.success) {{ alert(data.message); location.reload(); }} else {{ alert(\'Ошибка: \' + data.error); }} }}); '
                '}}">📤 Опубликовать</a>',
                publish_url
            )
        elif obj.pk and obj.status == 'published':
            return format_html('<span style="color: green;">✓ Опубликовано</span>')
        elif obj.pk and obj.status == 'failed':
            return format_html('<span style="color: red;">✗ Ошибка</span>')
        return '-'
    publish_now_button.short_description = "Действие"


class SocialAccountAdminForm(forms.ModelForm):
    """Кастомная форма для удобного ввода Telegram канала"""
    telegram_channel = forms.CharField(
        required=False,
        max_length=255,
        help_text='Telegram канал (например: @my_channel или -1001234567890)',
        label='Telegram канал'
    )

    class Meta:
        model = SocialAccount
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Если это Telegram и есть extra данные, показываем канал
        if self.instance.pk and self.instance.platform == 'telegram':
            if 'channel' in self.instance.extra:
                self.fields['telegram_channel'].initial = self.instance.extra.get('channel', '')

        # Подсказка для Telegram
        if self.instance.pk and self.instance.platform == 'telegram' or \
           ('platform' in self.initial and self.initial.get('platform') == 'telegram'):
            self.fields['access_token'].help_text = 'Для Telegram можно оставить пустым (используются настройки из Client)'

    def clean(self):
        cleaned_data = super().clean()

        # Если указан telegram_channel, сохраняем его в extra
        if cleaned_data.get('platform') == 'telegram':
            telegram_channel = cleaned_data.get('telegram_channel', '').strip()
            if telegram_channel:
                if 'extra' not in cleaned_data or not cleaned_data['extra']:
                    cleaned_data['extra'] = {}
                cleaned_data['extra']['channel'] = telegram_channel

        return cleaned_data


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    form = SocialAccountAdminForm
    list_display = ("client", "platform", "name", "telegram_channel_display")
    list_filter = ("platform", "client")
    search_fields = ("name", "client__name")
    autocomplete_fields = ("client",)

    fieldsets = (
        ("Основное", {
            "fields": ("client", "platform", "name"),
        }),
        ("Telegram настройки", {
            "fields": ("telegram_channel",),
            "description": "Для Telegram укажите канал (например: @my_channel)"
        }),
        ("API настройки", {
            "fields": ("access_token", "refresh_token", "extra"),
            "classes": ("collapse",),
        }),
    )

    def telegram_channel_display(self, obj):
        """Показать Telegram канал из extra"""
        if obj.platform == 'telegram' and obj.extra:
            channel = obj.extra.get('channel', '')
            if channel:
                return channel
        return '-'
    telegram_channel_display.short_description = "TG канал"


@admin.register(Connection)
class ConnectionAdmin(admin.ModelAdmin):
    list_display = ("client", "provider", "name", "account_id", "status", "expires_at", "updated_at")
    list_filter = ("provider", "status", "client")
    search_fields = ("name", "account_id", "provider_user_id", "client__name")
    readonly_fields = ("created_at", "updated_at", "last_error")
    autocomplete_fields = ("client", "created_by")
    fieldsets = (
        ("Основное", {"fields": ("client", "provider", "name", "status")}),
        ("Аккаунт", {"fields": ("provider_user_id", "account_id")}),
        ("Токены", {"fields": ("access_token", "refresh_token", "expires_at", "scopes")}),
        ("Метаданные", {"fields": ("metadata", "last_error", "created_by")}),
        ("Служебное", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(PostJob)
class PostJobAdmin(admin.ModelAdmin):
    list_display = ("id", "provider", "client", "connection", "status", "attempts", "created_at")
    list_filter = ("provider", "status", "client")
    search_fields = ("remote_id", "remote_url", "connection__name", "client__name")
    readonly_fields = ("created_at", "updated_at", "started_at", "finished_at")
    autocomplete_fields = ("client", "connection", "schedule")
    fieldsets = (
        ("Основное", {"fields": ("client", "provider", "connection", "schedule", "status", "attempts")}),
        ("Данные", {"fields": ("payload", "remote_id", "remote_url", "last_error")}),
        ("Время", {"fields": ("started_at", "finished_at", "created_at", "updated_at")}),
    )


class PostImageInline(admin.TabularInline):
    model = PostImage
    extra = 0
    fields = ("preview", "image", "alt_text", "order", "created_at")
    readonly_fields = ("preview", "created_at")

    def preview(self, obj):
        if obj and obj.image:
            return format_html('<img src="{}" style="width:80px;height:80px;object-fit:cover;border-radius:4px;" />', obj.image.url)
        return "-"
    preview.short_description = "Превью"


class PostVideoInline(admin.TabularInline):
    model = PostVideo
    extra = 0
    fields = ("preview", "video", "caption", "order", "created_at")
    readonly_fields = ("preview", "created_at")

    def preview(self, obj):
        video_url = _file_url_if_exists(getattr(obj, "video", None))
        if video_url:
            return format_html('<a href="{}" target="_blank">🎬 Смотреть</a>', video_url)
        if obj and getattr(obj, "video", None):
            return format_html('<span style="color:#d9534f;">⚠️ Файл отсутствует</span>')
        return "-"
    preview.short_description = "Видео"


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "client",
        "status",
        "story_link",
        "episode_number",
        "image_thumbnail",
        "video_badge",
        "created_at",
    )
    list_filter = ("client", "status", "story", "created_at")
    search_fields = ("title", "hook_title", "text", "client__name")
    autocomplete_fields = ("client", "created_by", "story")
    inlines = [PostImageInline, PostVideoInline, ScheduleInline]
    readonly_fields = (
        "story",
        "episode_number",
        "regeneration_count",
        "image_preview",
        "image_generate_button",
        "video_generate_button",
        "quick_publish_buttons",
        "regenerate_text_button",
        "wordstat_phrases_used",
    )

    actions = ["generate_image_action", "regenerate_text_action", "generate_videos_action"]

    fieldsets = (
        ("Базовая информация", {
            "fields": ("client", "title", "hook_title", "status", "tags", "wordstat_phrases_used"),
        }),
        ("Связь с историей", {
            "fields": ("story", "episode_number"),
            "classes": ("collapse",),
            "description": "Если этот пост - часть истории"
        }),
        ("Контент", {
            "fields": (
                "text",
                "regenerate_text_button",
                "regeneration_count",
                "image_generate_button",
                "image_preview",
                "video_generate_button",
            ),
        }),
        ("Публиковать", {
            "fields": (("publish_text", "publish_image", "publish_video"),),
            "description": "Выберите, какой контент включать в публикацию"
        }),
        ("Быстрая публикация", {
            "fields": ("quick_publish_buttons",),
            "description": "Опубликовать пост сейчас в выбранный канал (без создания расписания)"
        }),
    )

    def image_thumbnail(self, obj):
        """Миниатюра изображения для списка постов"""
        image = obj.get_primary_image()
        if image and image.image:
            return format_html('<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px;" />', image.image.url)
        return "-"
    image_thumbnail.short_description = "Image"

    def video_badge(self, obj):
        """Короткая ссылка на основное видео поста."""
        primary_video = obj.get_primary_video()
        if primary_video and primary_video.video:
            video_url = _file_url_if_exists(primary_video.video)
            if video_url:
                total = obj.videos.count()
                extra = f" ({total})" if total > 1 else ""
                return format_html('<a href="{}" target="_blank">🎬 Видео{}</a>', video_url, extra)
            return format_html('<span style="color:#d9534f;">⚠️ Нет файла</span>')
        return "-"
    video_badge.short_description = "Video"

    def image_preview(self, obj):
        """Превью изображения для страницы редактирования поста"""
        image = obj.get_primary_image()
        if image and image.image:
            extra = ""
            total = obj.images.count()
            if total > 1:
                extra = f"<div style='margin-top:6px;font-size:12px;color:#666;'>Ещё {total - 1} изображений в галерее ниже</div>"
            return format_html(
                '<div>{}<img src="{}" style="max-width: 400px; max-height: 400px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);" /></div>',
                mark_safe(extra),
                image.image.url
            )
        return "Нет изображений"
    image_preview.short_description = "Превью изображения"

    def image_generate_button(self, obj):
        """Кнопка для генерации изображения с помощью AI"""
        if obj.pk:  # Только для существующих постов
            generate_url = reverse('core:generate_post_image', args=[obj.pk])
            generation_method = get_image_generation_method()

            # Определяем текст и цвет кнопки в зависимости от метода
            method_configs = {
                'openrouter': {
                    'text': f"🖼️ Изображение (OpenRouter)",
                    'color': '#417690'
                },
                'veo_photo': {
                    'text': f"📸 Изображение (VEO)",
                    'color': '#5e35b1'
                },
                'giga_photo': {
                    'text': f"🎨 Изображение (Giga)",
                    'color': '#2e7d32'
                }
            }
            method_display_names = {
                'openrouter': f"OpenRouter ({get_image_generation_model()})",
                'veo_photo': 'VEO (Telegram бот)',
                'giga_photo': 'GigaChat (Telegram бот)'
            }

            config = method_configs.get(generation_method, method_configs['openrouter'])
            method_label = method_display_names.get(generation_method, generation_method)
            settings_url = reverse('admin:core_systemsetting_changelist')

            return format_html(
                '''
                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                    <button type="button" class="generate-image-btn" data-default-text="{}" data-method-label="{}" onclick="generateImage('{}', this)"
                    style="padding: 10px 15px; background-color: {}; color: white;
                    border: none; border-radius: 4px; cursor: pointer; font-size: 13px;">
                    {}</button>
                </div>
                <div style="margin-top: 6px; font-size: 12px; color: #6c757d;">
                    Используется метод <strong>{}</strong> из
                    <a href="{}" target="_blank" style="color: inherit; text-decoration: underline;">
                        системных настроек
                    </a>
                </div>
                <div id="generate-status" style="margin-top: 10px; font-size: 13px;"></div>
                <script>
                function getCookie(name) {{
                    let cookieValue = null;
                    if (document.cookie && document.cookie !== '') {{
                        const cookies = document.cookie.split(';');
                        for (let i = 0; i < cookies.length; i++) {{
                            const cookie = cookies[i].trim();
                            if (cookie.substring(0, name.length + 1) === (name + '=')) {{
                                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                                break;
                            }}
                        }}
                    }}
                    return cookieValue;
                }}

                function generateImage(baseUrl, clickedButton) {{
                    const buttons = document.querySelectorAll('.generate-image-btn');
                    const statusDiv = document.getElementById('generate-status');
                    const methodLabel = clickedButton.dataset.methodLabel || 'выбранный метод';

                    // Отключить все кнопки
                    buttons.forEach(btn => {{
                        btn.disabled = true;
                        btn.style.opacity = '0.6';
                    }});

                    clickedButton.textContent = 'Генерируется...';
                    statusDiv.innerHTML = '<span style="color: #007bff;">⏳ Генерация изображения началась (' + methodLabel + ')...</span>';

                    const csrftoken = getCookie('csrftoken');

                    fetch(baseUrl, {{
                        method: 'POST',
                        headers: {{
                            'X-CSRFToken': csrftoken,
                            'Content-Type': 'application/json',
                        }},
                        body: JSON.stringify({{}}),
                        credentials: 'same-origin'
                    }})
                    .then(response => {{
                        if (!response.ok) {{
                            return response.json().then(data => {{
                                throw new Error(data.error || 'Ошибка генерации');
                            }});
                        }}
                        return response.json();
                    }})
                    .then(data => {{
                        if (data.success) {{
                            statusDiv.innerHTML = '<span style="color: #28a745;">✓ ' + data.message + '</span>';
                            setTimeout(function() {{
                                location.reload();
                            }}, 3000);
                        }} else {{
                            throw new Error(data.error || 'Неизвестная ошибка');
                        }}
                    }})
                    .catch(error => {{
                        statusDiv.innerHTML = '<span style="color: #dc3545;">✗ Ошибка: ' + error.message + '</span>';

                        // Включить кнопки обратно
                        buttons.forEach(btn => {{
                            btn.disabled = false;
                            btn.style.opacity = '1';
                            if (btn.dataset.defaultText) {{
                                btn.textContent = btn.dataset.defaultText;
                            }}
                        }});
                    }});
                }}
                </script>
                ''',
                config["text"],
                method_label,
                generate_url,
                config["color"],
                config["text"],
                method_label,
                settings_url
            )
        return "Сохраните пост, чтобы сгенерировать изображение"
    image_generate_button.short_description = "AI фото"

    def video_generate_button(self, obj):
        """Кнопка генерации видео из текущего изображения поста."""
        if not obj or not obj.pk:
            return "Сохраните пост, чтобы создать видео"

        generate_url = reverse('core:generate_post_video', args=[obj.pk])
        veo_image_url = f"{generate_url}?method=veo&source=image"
        veo_text_url = f"{generate_url}?method=veo&source=text"
        status_id = f"generate-video-status-{obj.pk}"

        primary_image = obj.get_primary_image()
        image_disabled = '' if primary_image else 'disabled'
        text_disabled = '' if obj.text else 'disabled'
        image_title = '' if primary_image else 'title="Сначала добавьте изображение"'
        text_title = '' if obj.text else 'title="Нужен текст поста"'

        warnings = []
        if not primary_image:
            warnings.append('⚠️ Добавьте изображение (в инлайне ниже), чтобы сделать видео из картинки.')
        if not obj.text:
            warnings.append('⚠️ Добавьте текст, чтобы сделать видео по тексту.')

        warning_html = ''.join(
            f'<div style="color:#dc3545;font-size:12px;margin-top:4px;">{w}</div>' for w in warnings
        )

        return format_html(
            '''
            <div class="video-gen-section">
                <div style="display:flex; gap:8px; flex-wrap:wrap;">
                    <button type="button" class="generate-video-btn"
                        onclick="generatePostVideo('{image_url}', this, '{status_id}')"
                        style="padding: 8px 12px; background-color: #6a1b9a; color: white;
                        border: none; border-radius: 4px; cursor: pointer; font-size: 12px;"
                        {image_disabled} {image_title}>
                        🎬 VEO: из изображения
                    </button>
                    <button type="button" class="generate-video-btn"
                        onclick="generatePostVideo('{text_url}', this, '{status_id}')"
                        style="padding: 8px 12px; background-color: #1b5e20; color: white;
                        border: none; border-radius: 4px; cursor: pointer; font-size: 12px;"
                        {text_disabled} {text_title}>
                        📝 VEO: по тексту
                    </button>
                </div>
                <div id="{status_id}" style="margin-top: 8px; font-size: 13px;"></div>
                {warnings}
            </div>
            <script>
            if (!window.generatePostVideo) {{
                window.generatePostVideo = function(url, button, statusId) {{
                    const statusDiv = document.getElementById(statusId || 'generate-video-status');
                    const originalText = button.textContent;
                    button.disabled = true;
                    button.style.opacity = '0.6';
                    button.textContent = 'Генерация...';
                    statusDiv.innerHTML = '<span style="color: #007bff;">⏳ Генерация видео запущена...</span>';

                    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;

                    fetch(url, {{
                        method: 'POST',
                        headers: {{
                            'X-CSRFToken': csrftoken,
                            'Content-Type': 'application/json',
                        }},
                        credentials: 'same-origin'
                    }})
                    .then(response => response.json().then(data => [response.ok, data]))
                    .then(([ok, data]) => {{
                        if (!ok || !data.success) {{
                            throw new Error(data.error || 'Ошибка генерации видео');
                        }}
                        statusDiv.innerHTML = '<span style="color: #28a745;">✓ ' + data.message + '</span>';
                        setTimeout(() => window.location.reload(), 4000);
                    }})
                    .catch(error => {{
                        statusDiv.innerHTML = '<span style="color: #dc3545;">✗ ' + error.message + '</span>';
                        button.disabled = false;
                        button.style.opacity = '1';
                        button.textContent = originalText;
                    }});
                }}
            }}
            </script>
            ''',
            image_url=veo_image_url,
            text_url=veo_text_url,
            status_id=status_id,
            image_disabled=image_disabled,
            text_disabled=text_disabled,
            image_title=image_title,
            text_title=text_title,
            warnings=format_html(warning_html) if warnings else ''
        )
    video_generate_button.short_description = "AI видео"

    def quick_publish_buttons(self, obj):
        """Кнопки быстрой публикации в Telegram каналы"""
        if not obj.pk:
            return "Сохраните пост, чтобы использовать быструю публикацию"

        # Получаем все Telegram SocialAccount для клиента
        telegram_accounts = SocialAccount.objects.filter(
            client=obj.client,
            platform='telegram'
        )

        if not telegram_accounts.exists():
            return format_html(
                '<div style="color: #dc3545;">⚠️ Нет настроенных Telegram каналов для клиента "{}".<br>'
                'Добавьте Social Account в настройках клиента.</div>',
                obj.client.name
            )

        # Создаём URL для быстрой публикации
        quick_publish_url = reverse('core:quick_publish_post', args=[obj.pk])

        buttons_html = '<div style="display: flex; gap: 10px; flex-wrap: wrap; align-items: center;">'

        for account in telegram_accounts:
            channel_name = account.name
            channel_info = account.extra.get('channel', 'N/A') if account.extra else 'N/A'

            buttons_html += f'''
                <button type="button" class="quick-publish-btn"
                    onclick="quickPublish('{quick_publish_url}', {account.id}, '{channel_name}', this)"
                    style="padding: 8px 15px; background-color: #28a745; color: white;
                    border: none; border-radius: 4px; cursor: pointer; font-size: 13px;">
                    📤 {channel_name} ({channel_info})
                </button>
            '''

        buttons_html += '</div>'
        buttons_html += '<div id="quick-publish-status" style="margin-top: 10px; font-size: 13px;"></div>'
        buttons_html += '''
            <script>
            function quickPublish(url, accountId, channelName, button) {{
                const statusDiv = document.getElementById('quick-publish-status');
                const buttons = document.querySelectorAll('.quick-publish-btn');

                // Отключаем все кнопки
                buttons.forEach(btn => {{
                    btn.disabled = true;
                    btn.style.opacity = '0.6';
                }});

                button.textContent = 'Публикуется...';
                statusDiv.innerHTML = '<span style="color: #007bff;">⏳ Публикация в ' + channelName + '...</span>';

                // Получаем CSRF токен
                const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;

                fetch(url, {{
                    method: 'POST',
                    headers: {{
                        'X-CSRFToken': csrftoken,
                        'Content-Type': 'application/json',
                    }},
                    body: JSON.stringify({{ social_account_id: accountId }}),
                    credentials: 'same-origin'
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        statusDiv.innerHTML = '<span style="color: #28a745;">✓ ' + data.message + '</span>';
                        setTimeout(function() {{
                            location.reload();
                        }}, 2000);
                    }} else {{
                        throw new Error(data.error || 'Ошибка публикации');
                    }}
                }})
                .catch(error => {{
                    statusDiv.innerHTML = '<span style="color: #dc3545;">✗ Ошибка: ' + error.message + '</span>';

                    // Включаем кнопки обратно
                    buttons.forEach(btn => {{
                        btn.disabled = false;
                        btn.style.opacity = '1';
                    }});

                    // Восстанавливаем текст кнопки
                    button.textContent = '📤 ' + channelName;
                }});
            }}
            </script>
        '''

        return format_html(buttons_html)
    quick_publish_buttons.short_description = "Опубликовать сейчас"

    def story_link(self, obj):
        """Ссылка на историю"""
        if obj.story:
            url = reverse("admin:core_story_change", args=[obj.story.id])
            return format_html('<a href="{}">{} (эп. {})</a>', url, obj.story.title[:30], obj.episode_number)
        return "-"
    story_link.short_description = "История"

    def regenerate_text_button(self, obj):
        """Кнопка для регенерации текста поста"""
        if obj.pk:
            regenerate_url = reverse('core:regenerate_post_text', args=[obj.pk])
            return format_html(
                '''
                <button type="button" class="regenerate-text-btn"
                    onclick="regenerateText('{url}', this)"
                    style="padding: 10px 15px; background-color: #28a745; color: white;
                    border: none; border-radius: 4px; cursor: pointer; font-size: 13px;">
                    🔄 Обновить текст поста
                </button>
                <div id="regenerate-status" style="margin-top: 10px; font-size: 13px;"></div>
                <script>
                function getCookie(name) {{
                    let cookieValue = null;
                    if (document.cookie && document.cookie !== '') {{
                        const cookies = document.cookie.split(';');
                        for (let i = 0; i < cookies.length; i++) {{
                            const cookie = cookies[i].trim();
                            if (cookie.substring(0, name.length + 1) === (name + '=')) {{
                                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                                break;
                            }}
                        }}
                    }}
                    return cookieValue;
                }}

                function regenerateText(url, button) {{
                    const statusDiv = document.getElementById('regenerate-status');
                    const originalText = button.textContent;

                    // Disable button and show progress
                    button.disabled = true;
                    button.style.opacity = '0.6';
                    button.textContent = '⏳ Генерация...';
                    statusDiv.innerHTML = '<span style="color: #007bff;">⏳ Генерация нового текста...</span>';

                    fetch(url, {{
                        method: 'POST',
                        headers: {{
                            'X-CSRFToken': getCookie('csrftoken'),
                            'Content-Type': 'application/json'
                        }},
                        credentials: 'same-origin'
                    }})
                    .then(response => response.json().then(data => [response.ok, data]))
                    .then(([ok, data]) => {{
                        if (!ok || !data.success) {{
                            throw new Error(data.error || 'Ошибка регенерации текста');
                        }}
                        statusDiv.innerHTML = '<span style="color: #28a745;">✓ ' + data.message + '</span>';
                        setTimeout(() => window.location.reload(), 2000);
                    }})
                    .catch(error => {{
                        statusDiv.innerHTML = '<span style="color: #dc3545;">✗ ' + error.message + '</span>';
                        button.disabled = false;
                        button.style.opacity = '1';
                        button.textContent = originalText;
                    }});
                }}
                </script>
                ''',
                url=regenerate_url
            )
        return "Сохраните пост для регенерации"
    regenerate_text_button.short_description = "Регенерация"

    def generate_image_action(self, request, queryset):
        """Сгенерировать изображение для выбранных постов"""
        from .tasks import generate_image_for_post

        # Фильтровать только посты без изображений
        posts_without_images = queryset.filter(images__isnull=True)
        count = posts_without_images.count()

        if count == 0:
            self.message_user(request, "Все выбранные посты уже имеют изображения", level="warning")
            return

        # Запустить задачи генерации
        for post in posts_without_images:
            generate_image_for_post.delay(post.id)

        self.message_user(request, f"Запущена генерация изображений для {count} постов")
    generate_image_action.short_description = "Сгенерировать изображение для постов"

    def regenerate_text_action(self, request, queryset):
        """Регенерировать текст для выбранных постов"""
        from .tasks import regenerate_post_text

        count = queryset.count()

        if count == 0:
            self.message_user(request, "Выберите хотя бы один пост", level="warning")
            return

        # Запустить задачи регенерации
        for post in queryset:
            regenerate_post_text.delay(post.id)

        self.message_user(request, f"Запущена регенерация текста для {count} постов")
    regenerate_text_action.short_description = "🔄 Обновить текст постов"

    def generate_videos_action(self, request, queryset):
        """Сгенерировать два видео для каждого выбранного поста."""
        from .tasks import generate_videos_for_posts

        post_ids = list(queryset.values_list("id", flat=True))
        if not post_ids:
            self.message_user(request, "Выберите хотя бы один пост", level=messages.WARNING)
            return

        videos_per_post = 2
        generate_videos_for_posts.delay(post_ids, videos_per_post=videos_per_post)

        self.message_user(
            request,
            f"Запущена генерация {videos_per_post} видео для каждого из {len(post_ids)} постов",
            level=messages.SUCCESS
        )
    generate_videos_action.short_description = "Создать 2 видео на пост"


class ScheduleAdminForm(forms.ModelForm):
    """Кастомная форма для удобной публикации в Telegram каналы"""

    telegram_channels = forms.MultipleChoiceField(
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Telegram каналы',
        help_text='Выберите каналы для публикации'
    )

    class Meta:
        model = Schedule
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Автоопределение клиента из поста
        post = None

        # Способ 1: Parent Post передан через get_form в Inline
        if hasattr(self.__class__, 'parent_post') and self.__class__.parent_post:
            post = self.__class__.parent_post

        # Способ 2: Существующий Schedule с постом
        elif self.instance.pk and self.instance.post:
            post = self.instance.post

        # Способ 3: Post передан в initial (standalone форма)
        elif 'post' in self.initial:
            post_id = self.initial.get('post')
            if post_id:
                try:
                    post = Post.objects.get(id=post_id)
                except Post.DoesNotExist:
                    pass

        # Способ 4: Попробовать получить из instance.post (даже если pk нет)
        if not post and hasattr(self.instance, 'post') and self.instance.post:
            post = self.instance.post

        # Обработчик для динамического обновления при выборе поста (только для standalone формы)
        if 'post' in self.fields:
            self.fields['post'].widget.attrs['onchange'] = 'this.form.submit();'

        if post:
            client = post.client

            # Автоматически устанавливаем клиента (только если поле присутствует в форме)
            if 'client' in self.fields:
                self.fields['client'].initial = client
                self.fields['client'].disabled = True
                self.fields['client'].help_text = f'Автоматически определен из поста: {client.name}'

            # Получаем все Telegram SocialAccount для этого клиента
            telegram_accounts = SocialAccount.objects.filter(
                client=client,
                platform='telegram'
            )

            # Формируем choices для чекбоксов
            if 'telegram_channels' in self.fields:
                if telegram_accounts.exists():
                    choices = [(acc.id, f"{acc.name}") for acc in telegram_accounts]
                    self.fields['telegram_channels'].choices = choices
                    if 'social_account' in self.fields:
                        self.fields['social_account'].required = False
                        self.fields['social_account'].help_text = (
                            'Можно выбрать один канал здесь ИЛИ несколько в чекбоксах ниже'
                        )
                else:
                    # Если нет SocialAccount для Telegram
                    self.fields['telegram_channels'].widget = forms.HiddenInput()
                    self.fields['telegram_channels'].help_text = (
                        '⚠️ Создайте SocialAccount (platform=telegram) в админке для публикации в Telegram.'
                    )

            # Фильтруем social_account только по этому клиенту и Telegram
            if 'social_account' in self.fields:
                self.fields['social_account'].queryset = SocialAccount.objects.filter(
                    client=client,
                    platform='telegram'
                )
            if "connection" in self.fields:
                self.fields["connection"].queryset = Connection.objects.filter(client=client)

        # Если это существующий Schedule, скрываем telegram_channels
        if self.instance.pk and 'telegram_channels' in self.fields:
            self.fields['telegram_channels'].widget = forms.HiddenInput()
            self.fields['telegram_channels'].help_text = ''


# Подключаем форму к ScheduleInline после её определения
ScheduleInline.form = ScheduleAdminForm


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    form = ScheduleAdminForm
    list_display = ("post", "client", "social_account", "connection", "scheduled_at", "status", "quick_actions")
    list_filter = ("client", "social_account__platform", "connection__provider", "status", "scheduled_at")
    search_fields = ("post__title", "client__name", "social_account__name", "connection__name")
    autocomplete_fields = ("post",)
    readonly_fields = ("created_at", "log_display")

    actions = ["publish_now_action"]

    fieldsets = (
        ("Публикация", {
            "fields": ("post", "client", "telegram_channels", "social_account", "connection", "scheduled_at", "status"),
            "description": "Для публикации в несколько Telegram каналов выберите их в чекбоксах ниже"
        }),
        ("Результат публикации", {
            "fields": ("external_id", "log_display", "created_at"),
        }),
    )

    def quick_actions(self, obj):
        """Быстрые действия для публикации"""
        if obj.status == 'pending':
            return format_html(
                '<a class="button" href="#" onclick="publishNow({}); return false;" '
                'style="padding: 5px 10px; background-color: #417690; color: white; '
                'border-radius: 3px; text-decoration: none; font-size: 12px;">📤 Опубликовать сейчас</a>',
                obj.pk
            )
        elif obj.status == 'published':
            return format_html('<span style="color: green;">✓ Опубликовано</span>')
        elif obj.status == 'failed':
            return format_html('<span style="color: red;">✗ Ошибка</span>')
        return '-'
    quick_actions.short_description = "Действия"

    def log_display(self, obj):
        """Красивое отображение лога"""
        if obj.log:
            return format_html('<pre style="background: #f5f5f5; padding: 10px; border-radius: 5px;">{}</pre>', obj.log)
        return "Нет логов"
    log_display.short_description = "Лог публикации"

    def save_model(self, request, obj, form, change):
        """Обработка сохранения с созданием нескольких Schedule для разных каналов"""
        # Если это новый объект и выбраны telegram_channels
        if not change:
            selected_channels = form.cleaned_data.get('telegram_channels', [])

            if selected_channels:
                # Создаём Schedule для каждого выбранного канала
                created_count = 0
                for channel_id in selected_channels:
                    try:
                        social_account = SocialAccount.objects.get(id=int(channel_id))
                        Schedule.objects.create(
                            client=obj.client,
                            post=obj.post,
                            social_account=social_account,
                            scheduled_at=obj.scheduled_at,
                            status='pending'
                        )
                        created_count += 1
                    except (SocialAccount.DoesNotExist, ValueError):
                        pass

                if created_count > 0:
                    self.message_user(
                        request,
                        f'✓ Создано {created_count} расписаний для публикации в Telegram каналы',
                        level='success'
                    )
                    return  # Не сохраняем исходный объект

        # Стандартное сохранение для единичного Schedule
        super().save_model(request, obj, form, change)

    def publish_now_action(self, request, queryset):
        """Опубликовать выбранные посты сейчас"""
        from .tasks import publish_schedule
        from django.utils import timezone

        count = 0
        for schedule in queryset.filter(status='pending'):
            # Обновляем время на "сейчас"
            schedule.scheduled_at = timezone.now()
            schedule.save()

            # Запускаем публикацию
            publish_schedule.delay(schedule.id)
            count += 1

        if count > 0:
            self.message_user(request, f'Запущена публикация {count} постов')
        else:
            self.message_user(request, 'Нет постов для публикации (уже опубликованы или в процессе)', level='warning')

    publish_now_action.short_description = "📤 Опубликовать сейчас"

    class Media:
        js = ('admin/js/schedule_actions.js',)
        css = {
            'all': ('admin/css/schedule_admin.css',)
        }


class TrendItemInline(admin.TabularInline):
    model = TrendItem
    extra = 0
    fields = ("source", "title", "relevance_score", "discovered_at")
    readonly_fields = ("discovered_at",)
    can_delete = True


class TopicSEOKeywordSetInline(admin.TabularInline):
    model = SEOKeywordSet
    fk_name = "topic"
    extra = 0
    fields = ("group_type", "status", "keywords_preview", "created_at")
    readonly_fields = ("group_type", "status", "keywords_preview", "created_at")
    show_change_link = True
    can_delete = False

    def keywords_preview(self, obj):
        if obj.keywords_list:
            return ", ".join(obj.keywords_list[:3]) + ("..." if len(obj.keywords_list) > 3 else "")
        if obj.keyword_groups:
            preview = []
            for group_name, items in obj.keyword_groups.items():
                if isinstance(items, list):
                    preview.extend(items[:2])
            if preview:
                return ", ".join(preview[:3]) + ("..." if len(preview) > 3 else "")
        return "-"
    keywords_preview.short_description = "Ключи"


class TopicAdminForm(forms.ModelForm):
    """Кастомная форма для удобного ввода ключевых слов"""
    keywords_input = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'size': '80'}),
        help_text='Введите ключевые слова через запятую: танцы, хореография, dance',
        label='Ключевые слова'
    )

    class Meta:
        model = Topic
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Если есть существующие ключевые слова, показать их как текст
        if self.instance.pk and self.instance.keywords:
            self.fields['keywords_input'].initial = ', '.join(self.instance.keywords)
        # Скрыть оригинальное JSONField
        if 'keywords' in self.fields:
            self.fields['keywords'].widget = forms.HiddenInput()

    def clean(self):
        cleaned_data = super().clean()
        keywords_input = cleaned_data.get('keywords_input', '')

        # Конвертировать текст в список
        if keywords_input:
            keywords_list = [kw.strip() for kw in keywords_input.split(',') if kw.strip()]
            cleaned_data['keywords'] = keywords_list
        else:
            cleaned_data['keywords'] = []

        return cleaned_data


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    form = TopicAdminForm
    list_display = ("name", "client", "is_active", "sources_display", "keywords_display", "trend_count", "created_at")
    list_filter = ("client", "is_active", "created_at")
    search_fields = ("name", "client__name")
    autocomplete_fields = ("client",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [TrendItemInline, TopicSEOKeywordSetInline]

    actions = ["discover_content_action", "generate_posts_from_trends_action", "generate_seo_keywords_action"]

    fieldsets = (
        ("Основное", {
            "fields": ("client", "name", "is_active"),
        }),
        ("Параметры поиска", {
            "fields": ("keywords_input", "keywords"),
        }),
        ("Источники контента", {
            "fields": (
                "use_google_trends",
                "use_telegram",
                "use_rss",
                "use_youtube",
                "use_instagram",
                "use_vkontakte",
            ),
            "description": "Выберите источники, из которых искать контент при нажатии кнопки 'Найти'"
        }),
        ("Служебное", {
            "fields": ("created_at", "updated_at"),
        }),
    )

    def sources_display(self, obj):
        """Отображение включенных источников"""
        sources = []
        if obj.use_google_trends:
            sources.append("📈")
        if obj.use_telegram:
            sources.append("💬")
        if obj.use_rss:
            sources.append("📰")
        if obj.use_youtube:
            sources.append("▶️")
        if obj.use_instagram:
            sources.append("📷")
        if obj.use_vkontakte:
            sources.append("🔵")
        return " ".join(sources) if sources else "-"
    sources_display.short_description = "Источники"

    def keywords_display(self, obj):
        if obj.keywords:
            return ", ".join(obj.keywords[:3]) + ("..." if len(obj.keywords) > 3 else "")
        return "-"
    keywords_display.short_description = "Keywords"

    def trend_count(self, obj):
        return obj.trend_items.count()
    trend_count.short_description = "Trends"

    def discover_content_action(self, request, queryset):
        """Найти контент из выбранных источников"""
        from .tasks import discover_content_for_topic

        count = 0
        for topic in queryset:
            discover_content_for_topic.delay(topic.id)
            count += 1

        self.message_user(request, f"Запущен поиск контента для {count} тем из выбранных источников")
    discover_content_action.short_description = "🔍 Найти контент из выбранных источников"

    def generate_posts_from_trends_action(self, request, queryset):
        """Сгенерировать посты из всех неиспользованных трендов выбранных тем"""
        from .tasks import generate_posts_for_topic

        count = 0
        for topic in queryset:
            generate_posts_for_topic.delay(topic.id)
            count += 1

        self.message_user(request, f"Запущена генерация постов для {count} тем")
    generate_posts_from_trends_action.short_description = "Сгенерировать посты из неиспользованных трендов"

    def generate_seo_keywords_action(self, request, queryset):
        """Сгенерировать SEO-подборку ключевых фраз для клиентов выбранных тем"""
        from .tasks import generate_seo_keywords_for_client

        client_ids = set()
        count = 0
        for topic in queryset.select_related("client"):
            if topic.client_id not in client_ids:
                generate_seo_keywords_for_client.delay(topic.client_id)
                client_ids.add(topic.client_id)
                count += 1

        self.message_user(request, f"Запущена генерация SEO-фраз для {count} клиентов")
    generate_seo_keywords_action.short_description = "Сгенерировать SEO для клиентов выбранных тем"


@admin.register(TrendItem)
class TrendItemAdmin(admin.ModelAdmin):
    list_display = ("title_short", "source", "topic", "client", "relevance_score", "used", "discovered_at")
    list_filter = ("source", "client", "topic", "discovered_at")
    search_fields = ("title", "description", "topic__name", "client__name")
    autocomplete_fields = ("topic", "client", "used_for_post")
    readonly_fields = ("discovered_at",)

    actions = ["generate_posts_action", "generate_stories_action"]

    fieldsets = (
        ("Основное", {
            "fields": ("topic", "client", "source"),
        }),
        ("Содержание", {
            "fields": ("title", "description", "url", "relevance_score"),
        }),
        ("Дополнительно", {
            "fields": ("extra", "used_for_post", "discovered_at"),
        }),
    )
    def title_short(self, obj):
        return obj.title[:60] + "..." if len(obj.title) > 60 else obj.title
    title_short.short_description = "Title"

    def used(self, obj):
        return "✓" if obj.used_for_post else "-"
    used.short_description = "Used"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:trend_id>/custom-gen-video/",
                self.admin_site.admin_view(self.process_custom_gen_video_request),
                name="core_trenditem_custom_gen_video",
            ),
        ]
        return custom_urls + urls

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        context["has_description"] = bool((getattr(obj, "description", "") or "").strip())
        used_for_post_id = getattr(obj, "used_for_post_id", None) if obj else None
        context["used_for_post_id"] = used_for_post_id
        if used_for_post_id:
            try:
                context["used_for_post_change_url"] = reverse("admin:core_post_change", args=[used_for_post_id])
            except Exception:
                context["used_for_post_change_url"] = ""
        return super().render_change_form(request, context, add=add, change=change, form_url=form_url, obj=obj)

    def process_custom_gen_video_request(self, request, trend_id: int):
        change_url = reverse("admin:core_trenditem_change", args=[trend_id])
        trend = self.get_object(request, str(trend_id))

        if not trend:
            self.message_user(request, "Тренд не найден", level=messages.ERROR)
            return HttpResponseRedirect(reverse("admin:core_trenditem_changelist"))

        if request.method != "POST":
            return HttpResponseRedirect(change_url)

        if not self.has_change_permission(request, trend):
            raise PermissionDenied

        if not (getattr(trend, "description", "") or "").strip():
            self.message_user(
                request,
                "Description пустой — заполните Description и попробуйте снова.",
                level=messages.ERROR,
            )
            return HttpResponseRedirect(change_url)

        raw_videos_per_post = request.POST.get("videos_per_post")
        try:
            videos_per_post = int(raw_videos_per_post)
        except (TypeError, ValueError):
            videos_per_post = 1
        videos_per_post = max(1, videos_per_post)

        force_new_post = str(request.POST.get("force_new_post") or "").strip().lower() in {"1", "true", "on", "yes"}

        from .tasks import generate_videos_from_trend_item_description

        created_by_id = request.user.id if request.user and request.user.is_authenticated else None
        generate_videos_from_trend_item_description.delay(trend.id, videos_per_post, created_by_id, force_new_post)

        self.message_user(
            request,
            (
                f"Запущена генерация {videos_per_post} видео (3 сцены) по Description"
                + (" (создаст новый пост)" if force_new_post else "")
            ),
            level=messages.SUCCESS,
        )
        return HttpResponseRedirect(change_url)

    def generate_posts_action(self, request, queryset):
        """Сгенерировать посты из выбранных трендов"""
        from .tasks import generate_post_from_trend

        # Фильтровать только неиспользованные тренды
        unused_trends = queryset.filter(used_for_post__isnull=True)
        count = unused_trends.count()

        if count == 0:
            self.message_user(request, "Все выбранные тренды уже использованы", level="warning")
            return

        # Запустить задачи генерации
        for trend in unused_trends:
            generate_post_from_trend.delay(trend.id)

        self.message_user(request, f"Запущена генерация постов для {count} трендов")
    generate_posts_action.short_description = "Сгенерировать посты из выбранных трендов"

    def generate_stories_action(self, request, queryset):
        """Создать истории из выбранных трендов"""
        from .tasks import generate_story_from_trend

        count = queryset.count()

        if count == 0:
            self.message_user(request, "Выберите хотя бы один тренд", level="warning")
            return

        # Запустить задачи генерации историй (по умолчанию 5 эпизодов)
        for trend in queryset:
            generate_story_from_trend.delay(trend.id, episode_count=5)

        self.message_user(request, f"Запущена генерация историй для {count} трендов (по 5 эпизодов)")
    generate_stories_action.short_description = "📖 Создать истории из выбранных трендов"


class ContentTemplateAdminForm(forms.ModelForm):
    """Кастомная форма с dropdown из справочников PostType и PostTone"""

    class Meta:
        model = ContentTemplate
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Получаем admin_site и request из класса (установлены в get_form)
        admin_site = getattr(self.__class__, '_admin_site', None)
        request = getattr(self.__class__, '_request', None)

        # Импортируем модели здесь, чтобы избежать циклических импортов
        from .models import PostType, PostTone

        # Определяем клиента
        client = None
        if self.instance.pk:
            client = self.instance.client
        elif 'client' in self.initial:
            client = self.initial.get('client')
        elif request and hasattr(request.user, 'get_active_client'):
            # В форме добавления используем активного клиента пользователя
            try:
                client = request.user.get_active_client()
                # Устанавливаем клиента по умолчанию в форме
                if client and 'client' in self.fields:
                    self.fields['client'].initial = client
            except:
                pass

        # Получаем типы из справочника: системные (client=None) + клиентские
        if client:
            # Системные типы (доступны всем) + типы конкретного клиента
            post_types = PostType.objects.filter(
                models.Q(client__isnull=True) | models.Q(client=client)
            ).order_by('label')
        else:
            # Если клиент не определен, показываем только системные типы
            post_types = PostType.objects.filter(client__isnull=True).order_by('label')

        type_choices = [('', '---------')] + [(pt.value, pt.label) for pt in post_types]

        # Создаем виджет для типа
        type_widget = forms.Select(choices=type_choices)

        # Добавляем кнопку "+" если есть admin_site
        if admin_site:
            # Создаем fake relation для PostType
            rel = type('FakeRel', (), {
                'model': PostType,
                'get_related_field': lambda self=None: PostType._meta.pk,
                'limit_choices_to': {'client': client} if client else {},
            })()

            type_widget = admin_widgets.RelatedFieldWidgetWrapper(
                type_widget,
                rel,
                admin_site,
                can_add_related=True,
                can_change_related=False,
                can_delete_related=False,
            )

        self.fields['type'] = forms.CharField(
            widget=type_widget,
            help_text='Выберите тип из списка или нажмите "+" для добавления нового'
        )

        # Получаем тоны из справочника: системные (client=None) + клиентские
        if client:
            # Системные тоны (доступны всем) + тоны конкретного клиента
            post_tones = PostTone.objects.filter(
                models.Q(client__isnull=True) | models.Q(client=client)
            ).order_by('label')
        else:
            # Если клиент не определен, показываем только системные тоны
            post_tones = PostTone.objects.filter(client__isnull=True).order_by('label')

        tone_choices = [('', '---------')] + [(pt.value, pt.label) for pt in post_tones]

        # Создаем виджет для тона
        tone_widget = forms.Select(choices=tone_choices)

        # Добавляем кнопку "+" если есть admin_site
        if admin_site:
            # Создаем fake relation для PostTone
            rel = type('FakeRel', (), {
                'model': PostTone,
                'get_related_field': lambda self=None: PostTone._meta.pk,
                'limit_choices_to': {'client': client} if client else {},
            })()

            tone_widget = admin_widgets.RelatedFieldWidgetWrapper(
                tone_widget,
                rel,
                admin_site,
                can_add_related=True,
                can_change_related=False,
                can_delete_related=False,
            )

        self.fields['tone'] = forms.CharField(
            widget=tone_widget,
            help_text='Выберите тон из списка или нажмите "+" для добавления нового'
        )

        # Устанавливаем текущее значение, если редактируем
        if self.instance.pk:
            self.fields['type'].initial = self.instance.type
            self.fields['tone'].initial = self.instance.tone


@admin.register(ContentTemplate)
class ContentTemplateAdmin(admin.ModelAdmin):
    form = ContentTemplateAdminForm
    list_display = ("name", "client", "type", "tone", "length", "language", "is_default", "created_at")
    list_filter = ("client", "type", "tone", "length", "language", "is_default")
    search_fields = ("name", "client__name", "seo_prompt_template", "trend_prompt_template", "additional_instructions")
    autocomplete_fields = ("client",)
    readonly_fields = ("created_at", "updated_at")

    actions = ["copy_template_action"]

    fieldsets = (
        ("Основное", {
            "fields": ("client", "name", "type", "is_default"),
        }),
        ("Параметры стиля", {
            "fields": ("tone", "length", "language"),
        }),
        ("SEO промпт", {
            "fields": ("seo_prompt_template",),
            "description": (
                "Промпт для генерации контента на основе SEO ключевых фраз. "
                "Плейсхолдеры: {seo_keywords}, {topic_name}, {tone}, {length}, {language}, "
                "{type}, {avatar}, {pains}, {desires}, {objections}"
            )
        }),
        ("Trend промпт", {
            "fields": ("trend_prompt_template",),
            "description": (
                "Промпт для генерации контента на основе трендов. "
                "Плейсхолдеры: {trend_title}, {trend_description}, {trend_url}, {topic_name}, {tone}, {length}, {language}, "
                "{type}, {avatar}, {pains}, {desires}, {objections}"
            )
        }),
        ("Дополнительные инструкции", {
            "fields": ("additional_instructions",),
            "description": "Дополнительные инструкции для AI (применяются к обоим промптам)"
        }),
        ("Хэштеги", {
            "fields": ("include_hashtags", "max_hashtags"),
        }),
        ("Служебное", {
            "fields": ("created_at", "updated_at"),
        }),
    )

    def copy_template_action(self, request, queryset):
        """Скопировать выбранные шаблоны"""
        copied_count = 0

        for template in queryset:
            # Создаём копию, сбрасывая pk и уникальные поля
            template_copy = ContentTemplate(
                client=template.client,
                name=f"Копия - {template.name}",
                type=template.type,
                tone=template.tone,
                length=template.length,
                language=template.language,
                seo_prompt_template=template.seo_prompt_template,
                trend_prompt_template=template.trend_prompt_template,
                additional_instructions=template.additional_instructions,
                is_default=False,  # Копия не может быть default
                include_hashtags=template.include_hashtags,
                max_hashtags=template.max_hashtags,
            )

            # Проверяем уникальность имени
            original_name = template_copy.name
            counter = 1
            while ContentTemplate.objects.filter(
                client=template.client,
                name=template_copy.name
            ).exists():
                template_copy.name = f"{original_name} ({counter})"
                counter += 1

            template_copy.save()
            copied_count += 1

        self.message_user(
            request,
            f"Успешно скопировано шаблонов: {copied_count}"
        )

    copy_template_action.short_description = "Копировать выбранные шаблоны"

    def get_form(self, request, obj=None, **kwargs):
        """Передаем admin_site и request в форму для использования RelatedFieldWidgetWrapper"""
        form = super().get_form(request, obj, **kwargs)
        form._admin_site = self.admin_site
        form._request = request
        return form


@admin.register(SEOKeywordSet)
class SEOKeywordSetAdmin(admin.ModelAdmin):
    MAX_POSTS_PER_RUN = 99

    list_display = ("group_type", "topic", "client", "status", "keywords_count", "ai_model", "created_at")
    list_filter = ("group_type", "status", "client", "created_at")
    search_fields = ("topic__name", "client__name", "keywords_text")
    autocomplete_fields = ("topic", "client")
    readonly_fields = ("created_at", "updated_at", "keywords_display", "generate_posts_block")

    fieldsets = (
        ("Основное", {
            "fields": ("group_type", "topic", "client", "status"),
        }),
        ("SEO-фразы", {
            "fields": ("keywords_list", "keyword_groups", "keywords_display"),
            "description": "Сгенерированные фразы (новые записи используют поле 'keywords_list')"
        }),
        ("Создать посты", {
            "fields": ("generate_posts_block",),
            "description": "Сгенерируйте серию постов по выбранному SEO шаблону",
        }),
        ("Техническая информация", {
            "fields": ("ai_model", "prompt_used", "error_log"),
            "classes": ("collapse",),
        }),
        ("Служебное", {
            "fields": ("created_at", "updated_at"),
        }),
    )

    def keywords_count(self, obj):
        if not obj:
            return 0
        return len(obj.get_flat_keywords())
    keywords_count.short_description = "Количество"

    def keywords_display(self, obj):
        """Универсальное отображение ключей (список или группы)."""
        if obj.keywords_list:
            html = '<div style="font-family: monospace; background: #f5f5f5; padding: 15px; border-radius: 5px;">'
            html += '<ul style="margin: 0;">'
            for keyword in obj.keywords_list:
                html += f'<li>{keyword}</li>'
            html += '</ul></div>'
            return format_html(html)
        if obj.keyword_groups:
            html = '<div style="font-family: monospace; background: #f5f5f5; padding: 15px; border-radius: 5px;">'
            for group_name, keywords in obj.keyword_groups.items():
                html += f'<h4 style="color: #417690; margin-top: 10px;">{group_name.upper()}</h4>'
                if isinstance(keywords, list):
                    html += '<ul style="margin: 5px 0;">'
                    for keyword in keywords:
                        html += f'<li>{keyword}</li>'
                    html += '</ul>'
            html += '</div>'
            return format_html(html)
        return "Ключи не сгенерированы"
    keywords_display.short_description = "Сгенерированные ключи"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:seo_set_id>/generate-posts/",
                self.admin_site.admin_view(self.process_generate_posts_request),
                name="core_seokeywordset_generate_posts",
            ),
            path(
                "<int:seo_set_id>/generate-posts-videos/",
                self.admin_site.admin_view(self.process_generate_posts_with_videos_request),
                name="core_seokeywordset_generate_posts_videos",
            ),
        ]
        return custom_urls + urls

    def change_view(self, request, object_id, form_url="", extra_context=None):
        self._current_request = request
        response = super().change_view(request, object_id, form_url, extra_context)

        def cleanup(resp):
            setattr(self, "_current_request", None)
            return resp

        if hasattr(response, "add_post_render_callback"):
            response.add_post_render_callback(cleanup)
        else:
            cleanup(response)
        return response

    def generate_posts_block(self, obj):
        request = getattr(self, "_current_request", None)
        if not obj or not obj.pk:
            return "Сохраните SEO подборку, чтобы создать посты"
        if not obj.client:
            return "Не указан клиент для этой SEO подборки"

        keywords = obj.get_flat_keywords()
        keyword_count = len(keywords)
        if keyword_count == 0:
            return format_html('<div style="color:#ba2121;">Добавьте или сгенерируйте ключи выше.</div>')

        templates = list(
            ContentTemplate.objects
            .for_client(obj.client)
            .select_related("client")
            .order_by("name")
        )

        templates.sort(
            key=lambda tpl: (
                0 if tpl.client_id == obj.client_id else 1,
                tpl.name.lower(),
            )
        )
        if not templates:
            return format_html(
                '<div style="color:#ba2121;">Нет доступных контент-шаблонов. '
                'Добавьте шаблон клиенту или создайте системный шаблон.</div>'
            )

        if not request:
            return "Форма недоступна в текущем контексте"

        posts_action_url = reverse("admin:core_seokeywordset_generate_posts", args=[obj.pk])
        videos_action_url = reverse("admin:core_seokeywordset_generate_posts_videos", args=[obj.pk])
        max_posts = self.MAX_POSTS_PER_RUN
        context = {
            "posts_action_url": posts_action_url,
            "videos_action_url": videos_action_url,
            "csrf_token": get_token(request),
            "templates": templates,
            "default_posts_count": min(keyword_count, max_posts) or 1,
            "default_video_posts_count": min(keyword_count, max_posts) or 1,
            "default_videos_per_post": 1,
            "keyword_count": keyword_count,
            "max_posts": max_posts,
        }
        html = render_to_string("admin/core/seo_keyword_set/generate_posts_block.html", context)
        return mark_safe(html)

    generate_posts_block.short_description = "Создать посты"

    def process_generate_posts_request(self, request, seo_set_id: int):
        change_url = reverse("admin:core_seokeywordset_change", args=[seo_set_id])
        seo_set = self.get_object(request, str(seo_set_id))

        if not seo_set:
            self.message_user(
                request,
                "SEO подборка не найдена",
                level=messages.ERROR
            )
            return HttpResponseRedirect(reverse("admin:core_seokeywordset_changelist"))

        if request.method != "POST":
            return HttpResponseRedirect(change_url)

        if not self.has_change_permission(request, seo_set):
            raise PermissionDenied

        keywords = seo_set.get_flat_keywords()
        if not keywords:
            self.message_user(
                request,
                "Нет ключевых фраз для генерации постов",
                level=messages.ERROR
            )
            return HttpResponseRedirect(change_url)

        template_id = request.POST.get("template_id")
        if not template_id:
            self.message_user(
                request,
                "Выберите шаблон контента",
                level=messages.ERROR
            )
            return HttpResponseRedirect(change_url)

        try:
            template = ContentTemplate.get_for_client_or_system(seo_set.client, template_id)
        except ContentTemplate.DoesNotExist:
            self.message_user(
                request,
                "Шаблон не найден или недоступен этому клиенту",
                level=messages.ERROR
            )
            return HttpResponseRedirect(change_url)

        raw_posts_count = request.POST.get("posts_count")
        try:
            posts_count = int(raw_posts_count)
        except (TypeError, ValueError):
            posts_count = len(keywords)

        posts_count = max(1, min(self.MAX_POSTS_PER_RUN, posts_count))

        if posts_count <= 0:
            self.message_user(
                request,
                "Количество постов должно быть положительным",
                level=messages.ERROR
            )
            return HttpResponseRedirect(change_url)

        from .tasks import generate_posts_from_seo_keyword_set

        created_by_id = request.user.id if request.user and request.user.is_authenticated else None

        generate_posts_from_seo_keyword_set.delay(
            seo_set.id,
            template.id,
            posts_count,
            created_by_id
        )

        self.message_user(
            request,
            f"Запущена генерация {posts_count} постов по шаблону «{template.name}»",
            level=messages.SUCCESS
        )
        return HttpResponseRedirect(change_url)

    def process_generate_posts_with_videos_request(self, request, seo_set_id: int):
        change_url = reverse("admin:core_seokeywordset_change", args=[seo_set_id])
        seo_set = self.get_object(request, str(seo_set_id))

        if not seo_set:
            self.message_user(
                request,
                "SEO подборка не найдена",
                level=messages.ERROR
            )
            return HttpResponseRedirect(reverse("admin:core_seokeywordset_changelist"))

        if request.method != "POST":
            return HttpResponseRedirect(change_url)

        if not self.has_change_permission(request, seo_set):
            raise PermissionDenied

        keywords = seo_set.get_flat_keywords()
        if not keywords:
            self.message_user(
                request,
                "Нет ключевых фраз для генерации постов",
                level=messages.ERROR
            )
            return HttpResponseRedirect(change_url)

        template_id = request.POST.get("template_id")
        if not template_id:
            self.message_user(
                request,
                "Выберите шаблон контента",
                level=messages.ERROR
            )
            return HttpResponseRedirect(change_url)

        try:
            template = ContentTemplate.get_for_client_or_system(seo_set.client, template_id)
        except ContentTemplate.DoesNotExist:
            self.message_user(
                request,
                "Шаблон не найден или недоступен этому клиенту",
                level=messages.ERROR
            )
            return HttpResponseRedirect(change_url)

        raw_posts_count = request.POST.get("posts_count")
        try:
            posts_count = int(raw_posts_count)
        except (TypeError, ValueError):
            posts_count = len(keywords)
        posts_count = max(1, min(self.MAX_POSTS_PER_RUN, posts_count))

        raw_videos_per_post = request.POST.get("videos_per_post")
        try:
            videos_per_post = int(raw_videos_per_post)
        except (TypeError, ValueError):
            videos_per_post = 1
        videos_per_post = max(1, videos_per_post)

        from .tasks import generate_posts_with_videos_from_seo_keyword_set

        created_by_id = request.user.id if request.user and request.user.is_authenticated else None

        generate_posts_with_videos_from_seo_keyword_set.delay(
            seo_set.id,
            template.id,
            posts_count,
            videos_per_post,
            created_by_id
        )

        self.message_user(
            request,
            (
                f"Запущена генерация {posts_count} постов "
                f"с {videos_per_post} видео(роликами) на ключ для шаблона «{template.name}»"
            ),
            level=messages.SUCCESS
        )
        return HttpResponseRedirect(change_url)


# ============================================================================
# STORY ADMIN (Истории - мини-сериалы)
# ============================================================================

class StoryPostInline(admin.TabularInline):
    """Inline для отображения постов истории"""
    model = Post
    extra = 0
    fields = ("episode_number", "title", "status", "regeneration_count", "view_post_link")
    readonly_fields = ("episode_number", "title", "status", "regeneration_count", "view_post_link")
    can_delete = False
    show_change_link = True

    def view_post_link(self, obj):
        if obj.id:
            url = reverse("admin:core_post_change", args=[obj.id])
            return format_html('<a href="{}">Редактировать пост</a>', url)
        return "-"
    view_post_link.short_description = "Действия"


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ("title", "client", "episode_count", "posts_count", "status", "trend_item_link", "created_at")
    list_filter = ("status", "client", "created_at")
    search_fields = ("title", "client__name")
    autocomplete_fields = ("client", "trend_item", "template")
    readonly_fields = ("generated_by", "created_at", "updated_at", "episodes_display", "posts_count")
    inlines = [StoryPostInline]

    fieldsets = (
        ("Основная информация", {
            "fields": ("client", "title", "status"),
        }),
        ("Источник и настройки", {
            "fields": ("trend_item", "template", "episode_count"),
        }),
        ("Эпизоды истории", {
            "fields": ("episodes", "episodes_display"),
            "description": "Список эпизодов сгенерированной истории"
        }),
        ("Техническая информация", {
            "fields": ("generated_by", "posts_count", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    actions = ["generate_posts_action", "create_auto_schedule_action"]

    def trend_item_link(self, obj):
        """Ссылка на тренд"""
        if obj.trend_item:
            url = reverse("admin:core_trenditem_change", args=[obj.trend_item.id])
            return format_html('<a href="{}">{}</a>', url, obj.trend_item.title[:40])
        return "-"
    trend_item_link.short_description = "Исходный тренд"

    def posts_count(self, obj):
        """Количество созданных постов"""
        return obj.posts.count()
    posts_count.short_description = "Создано постов"

    def episodes_display(self, obj):
        """Красивое отображение эпизодов"""
        if obj.episodes:
            html = '<div style="font-family: monospace; background: #f5f5f5; padding: 10px; border-radius: 5px;">'
            html += '<ol style="margin: 0; padding-left: 20px;">'
            for episode in obj.episodes:
                html += f'<li style="margin: 5px 0;"><strong>Эпизод {episode["order"]}:</strong> {episode["title"]}</li>'
            html += '</ol>'
            html += '</div>'
            return format_html(html)
        return "Эпизоды не сгенерированы"
    episodes_display.short_description = "Список эпизодов"

    def generate_posts_action(self, request, queryset):
        """Создать посты из эпизодов"""
        from .tasks import generate_posts_from_story

        generated_count = 0
        for story in queryset:
            if story.status in ["ready", "approved"]:
                generate_posts_from_story.delay(story.id)
                generated_count += 1
            else:
                self.message_user(
                    request,
                    f"История '{story.title}' имеет статус {story.status}, нужен статус 'ready' или 'approved'",
                    level="WARNING"
                )

        if generated_count > 0:
            self.message_user(
                request,
                f"Запущена генерация постов для {generated_count} историй"
            )

    generate_posts_action.short_description = "🎬 Создать посты из эпизодов"

    def create_auto_schedule_action(self, request, queryset):
        """Создать автоматическое расписание"""
        if queryset.count() != 1:
            self.message_user(
                request,
                "Выберите только одну историю для создания расписания",
                level="ERROR"
            )
            return

        story = queryset.first()

        # Перенаправляем на форму создания расписания
        # TODO: Реализовать кастомную форму для настройки расписания
        self.message_user(
            request,
            f"Для создания расписания используйте кнопку в интерфейсе редактирования истории '{story.title}'",
            level="INFO"
        )

    create_auto_schedule_action.short_description = "📅 Создать автоматическое расписание"


CORE_ADMIN_MODEL_ORDER = {
    "Client": 0,
    "Topic": 1,
    "TrendItem": 2,
    "Post": 3,
    "SEOKeywordSet": 4,
    "ProductTypeAdminProxy": 5,
    "Article": 6,
    "Articles": 7,
    "SystemSetting": 999,
}


def _core_model_sort_key(model_dict):
    return (
        CORE_ADMIN_MODEL_ORDER.get(model_dict["object_name"], 100),
        model_dict["name"],
    )


_original_get_app_list = admin.site.get_app_list


def _core_sorted_get_app_list(*args, **kwargs):
    """Wrap admin get_app_list to enforce custom ordering for core models."""
    app_list = _original_get_app_list(*args, **kwargs)
    if isinstance(app_list, list):
        for app in app_list:
            if app.get("app_label") == "core":
                app["models"].sort(key=_core_model_sort_key)
    return app_list


if not getattr(admin.site, "_core_sorted", False):
    admin.site.get_app_list = _core_sorted_get_app_list
    admin.site._core_sorted = True


class ProductTypeAdminProxy(ProductType):
    class Meta:
        proxy = True
        verbose_name = "Тип продукта"
        verbose_name_plural = "Типы продуктов"


@admin.register(ProductTypeAdminProxy)
class ProductTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "owner", "updated_at")
    list_select_related = ("owner",)
    list_filter = ("owner", "updated_at")
    search_fields = ("name", "value", "goal", "owner__name", "owner__slug")
    autocomplete_fields = ("owner",)
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Основное", {"fields": ("owner", "name")}),
        ("Маркетинг", {"fields": ("value", "goal")}),
        (
            "AI требования (9 блоков)",
            {
                "fields": (
                    "requirements_name",
                    "requirements_packages",
                    "requirements_audience",
                    "requirements_transformation",
                    "requirements_metrics",
                    "requirements_method",
                    "requirements_lesson_format",
                    "requirements_program_modules",
                    "requirements_packaging",
                ),
                "classes": ("collapse",),
            },
        ),
        ("Системное", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(PostType)
class PostTypeAdmin(admin.ModelAdmin):
    """Админка для справочника типов постов"""
    list_display = ("label", "value", "client_display", "is_default", "created_at")
    list_filter = ("client", "is_default", "created_at")
    search_fields = ("label", "value", "client__name")
    autocomplete_fields = ("client",)
    readonly_fields = ("created_at",)

    fieldsets = (
        ("Основная информация", {
            "fields": ("client", "label", "value", "is_default"),
            "description": "Оставьте поле 'Client' пустым для создания системного типа, доступного всем клиентам"
        }),
        ("Системная информация", {
            "fields": ("created_at",),
            "classes": ("collapse",),
        }),
    )

    def client_display(self, obj):
        """Показывает 'Системный' если client=None"""
        return obj.client.name if obj.client else "Системный"
    client_display.short_description = "Client"
    client_display.admin_order_field = "client"


@admin.register(PostTone)
class PostToneAdmin(admin.ModelAdmin):
    """Админка для справочника тонов постов"""
    list_display = ("label", "value", "client_display", "is_default", "created_at")
    list_filter = ("client", "is_default", "created_at")
    search_fields = ("label", "value", "client__name")
    autocomplete_fields = ("client",)
    readonly_fields = ("created_at",)

    fieldsets = (
        ("Основная информация", {
            "fields": ("client", "label", "value", "is_default"),
            "description": "Оставьте поле 'Client' пустым для создания системного тона, доступного всем клиентам"
        }),
        ("Системная информация", {
            "fields": ("created_at",),
            "classes": ("collapse",),
        }),
    )

    def client_display(self, obj):
        """Показывает 'Системный' если client=None"""
        return obj.client.name if obj.client else "Системный"
    client_display.short_description = "Client"
    client_display.admin_order_field = "client"
