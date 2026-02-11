from django.conf import settings
from django.db import models

from .client import Client
from .integrations import Connection, SocialAccount


class PostJob(models.Model):
    """Задача публикации для очереди."""

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("succeeded", "Succeeded"),
        ("failed", "Failed"),
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="post_jobs")
    provider = models.CharField(max_length=30, choices=Connection.PROVIDER_CHOICES)
    connection = models.ForeignKey(
        Connection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="post_jobs",
    )
    schedule = models.ForeignKey(
        "Schedule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="post_jobs",
    )
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    remote_id = models.CharField(max_length=255, blank=True)
    remote_url = models.TextField(blank=True)
    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.provider} job #{self.id} ({self.status})"


class Post(models.Model):
    STATUS_CHOICES = (
        ("draft", "Draft"),        # черновик, только что создан
        ("ready", "Ready"),        # AI сгенерировал, но человек не смотрел
        ("approved", "Approved"),  # человек утвердил
        ("scheduled", "Scheduled"), # есть задания в Schedule
        ("published", "Published"), # полностью выпущен
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="posts")
    story = models.ForeignKey(
        "Story",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="posts",
        help_text="История, к которой относится этот пост",
    )
    template = models.ForeignKey(
        "ContentTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="posts",
        help_text="Шаблон, использованный для генерации поста",
    )
    episode_number = models.IntegerField(null=True, blank=True, help_text="Номер эпизода в истории")

    title = models.CharField(max_length=255)
    hook_title = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Цепляющий заголовок (для фото)",
        help_text="Короткий заголовок до 3 слов для нанесения на изображение",
    )
    text = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    tags = models.JSONField(default=list, blank=True)
    source_links = models.JSONField(default=list, blank=True)
    wordstat_phrases_used = models.JSONField(
        default=list,
        blank=True,
        help_text="Какие избранные фразы Wordstat были использованы при генерации",
    )

    publish_text = models.BooleanField(default=True, verbose_name="Публиковать текст")
    publish_image = models.BooleanField(default=True, verbose_name="Публиковать изображение")
    publish_video = models.BooleanField(default=True, verbose_name="Публиковать видео")

    generated_by = models.CharField(max_length=50, blank=True)
    regeneration_count = models.IntegerField(default=0, help_text="Количество регенераций текста")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_posts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"[{self.client.slug}] {self.title}"

    def get_primary_image(self):
        return self.images.order_by("order", "id").first()

    def get_primary_video(self):
        return self.videos.order_by("order", "id").first()


class PostImage(models.Model):
    """Изображение поста (поддержка нескольких файлов)."""

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="post_images/")
    alt_text = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("order", "id")
        verbose_name = "Post Image"
        verbose_name_plural = "Post Images"

    def __str__(self):
        return f"Image #{self.id} for {self.post}"


class PostVideo(models.Model):
    """Видео поста (поддержка нескольких файлов)."""

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="videos")
    video = models.FileField(upload_to="post_videos/")
    caption = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("order", "id")
        verbose_name = "Post Video"
        verbose_name_plural = "Post Videos"

    def __str__(self):
        return f"Video #{self.id} for {self.post}"


class VeoVideoExport(models.Model):
    """Архив выгруженных VEO-видео на Яндекс.Диск."""

    disk_path = models.CharField(max_length=1024, unique=True)
    request_text = models.TextField(
        blank=True,
        help_text='Фрагмент ответа VEO: от "Ваш запрос:" до "🎛️ Инструмент:"',
    )
    telegram_message_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    telegram_message_date = models.DateTimeField(null=True, blank=True)
    bot_username = models.CharField(max_length=255, blank=True, db_index=True)
    source_url = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "VEO Video Export"
        verbose_name_plural = "VEO Video Exports"

    def __str__(self):
        return self.disk_path


class Schedule(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("in_progress", "In progress"),
        ("published", "Published"),
        ("failed", "Failed"),
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="schedules")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="schedules")
    social_account = models.ForeignKey(
        SocialAccount,
        on_delete=models.CASCADE,
        related_name="schedules",
        null=True,
        blank=True,
    )
    connection = models.ForeignKey(
        Connection,
        on_delete=models.SET_NULL,
        related_name="schedules",
        null=True,
        blank=True,
        help_text="Предпочтительное подключение для публикации",
    )
    scheduled_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    external_id = models.CharField(max_length=255, blank=True, help_text="ID поста в соцсети (если есть)")
    log = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("scheduled_at",)

    def __str__(self):
        target = self.connection or self.social_account
        return f"{self.post} -> {target} @ {self.scheduled_at} ({self.status})"
