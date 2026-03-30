"""
Модели с managed=False — зеркалят таблицы из схем map.* и chains.*.
Django не управляет миграциями этих таблиц.
"""
import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone

from .client import Client


# ============================================================================
# Products (map.product_types, map.products)
# ============================================================================

class ProductType(models.Model):
    owner = models.ForeignKey(Client, on_delete=models.CASCADE, db_column="owner_id", related_name="product_types")
    name = models.TextField()
    value = models.TextField(blank=True, null=True)
    goal = models.TextField(blank=True, null=True)
    requirements_name = models.TextField(blank=True, null=True)
    requirements_packages = models.TextField(blank=True, null=True)
    requirements_audience = models.TextField(blank=True, null=True)
    requirements_transformation = models.TextField(blank=True, null=True)
    requirements_metrics = models.TextField(blank=True, null=True)
    requirements_method = models.TextField(blank=True, null=True)
    requirements_lesson_format = models.TextField(blank=True, null=True)
    requirements_program_modules = models.TextField(blank=True, null=True)
    requirements_packaging = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'map"."product_types'
        ordering = ("-updated_at",)

    def __str__(self):
        return self.name


class ClientProduct(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_ACTIVE = "active"
    STATUS_CHOICES = (
        (STATUS_DRAFT, "Черновик"),
        (STATUS_ACTIVE, "Активный"),
    )

    owner = models.ForeignKey(Client, on_delete=models.CASCADE, db_column="owner_id", related_name="products")
    name = models.TextField()
    product_type = models.ForeignKey(
        ProductType, on_delete=models.SET_NULL, db_column="product_type_id",
        related_name="products", blank=True, null=True,
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    short_description = models.TextField(blank=True, null=True)
    packages = models.JSONField(default=list, blank=True)
    structure = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'map"."products'
        ordering = ("-updated_at",)

    def __str__(self):
        return self.name


# ============================================================================
# Product LMS (map.product_course_*)
# ============================================================================

class ProductCourse(models.Model):
    owner = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        db_column="owner_id",
        related_name="product_courses",
    )
    product = models.OneToOneField(
        ClientProduct,
        on_delete=models.CASCADE,
        db_column="product_id",
        related_name="course",
    )
    title = models.TextField()
    description = models.TextField(blank=True, null=True)
    cover_url = models.TextField(blank=True, null=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'map"."product_courses'
        ordering = ("-updated_at", "-id")

    def __str__(self):
        return self.title


class ProductCourseModule(models.Model):
    LESSON_UNLOCK_AFTER_STUDENT_COMPLETE = "after_student_complete"
    LESSON_UNLOCK_AFTER_CURATOR_COMPLETE = "after_curator_complete"
    LESSON_UNLOCK_AFTER_TIMER = "after_timer"
    LESSON_UNLOCK_CONDITION_CHOICES = (
        (LESSON_UNLOCK_AFTER_STUDENT_COMPLETE, "После отметки завершения урока"),
        (LESSON_UNLOCK_AFTER_CURATOR_COMPLETE, "После отметки куратора"),
        (LESSON_UNLOCK_AFTER_TIMER, "По таймеру после завершения"),
    )

    course = models.ForeignKey(
        ProductCourse,
        on_delete=models.CASCADE,
        db_column="course_id",
        related_name="modules",
    )
    title = models.TextField()
    cover_url = models.TextField(blank=True, null=True)
    position = models.IntegerField(default=0)
    unlock_at = models.DateTimeField(blank=True, null=True)
    open_lessons_immediately = models.BooleanField(default=False)
    lesson_unlock_condition = models.CharField(
        max_length=32,
        choices=LESSON_UNLOCK_CONDITION_CHOICES,
        default=LESSON_UNLOCK_AFTER_STUDENT_COMPLETE,
    )
    unlock_delay_days = models.IntegerField(default=0)
    unlock_delay_hours = models.IntegerField(default=0)
    unlock_delay_minutes = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'map"."product_course_modules'
        ordering = ("position", "id")

    def __str__(self):
        return self.title


class ProductCourseLesson(models.Model):
    module = models.ForeignKey(
        ProductCourseModule,
        on_delete=models.CASCADE,
        db_column="module_id",
        related_name="lessons",
    )
    title = models.TextField()
    content = models.JSONField(default=dict, blank=True)
    position = models.IntegerField(default=0)
    is_preview = models.BooleanField(default=False)
    unlock_at = models.DateTimeField(blank=True, null=True)
    youtube_video_id = models.CharField(max_length=64, blank=True, null=True)
    rutube_video_id = models.CharField(max_length=128, blank=True, null=True)
    vk_owner_id = models.CharField(max_length=64, blank=True, null=True)
    vk_video_id = models.CharField(max_length=64, blank=True, null=True)
    vk_hash = models.CharField(max_length=128, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'map"."product_course_lessons'
        ordering = ("position", "id")

    def __str__(self):
        return self.title


class ProductCourseProgress(models.Model):
    owner = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        db_column="owner_id",
        related_name="product_course_progress_items",
    )
    contact_id = models.BigIntegerField(db_index=True)
    lesson = models.ForeignKey(
        ProductCourseLesson,
        on_delete=models.CASCADE,
        db_column="lesson_id",
        related_name="progress_items",
    )
    completed_at = models.DateTimeField(default=timezone.now)
    curator_completed_at = models.DateTimeField(blank=True, null=True)
    curator_user_id = models.BigIntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'map"."product_course_progress'
        unique_together = ("owner", "contact_id", "lesson")
        ordering = ("-completed_at", "-id")


class ProductCourseEvent(models.Model):
    EVENT_LESSON_COMPLETED = "lesson_completed"
    EVENT_LESSON_ACCEPTED = "lesson_accepted"
    EVENT_TYPE_CHOICES = (
        (EVENT_LESSON_COMPLETED, "Урок завершен учеником"),
        (EVENT_LESSON_ACCEPTED, "Урок принят куратором"),
    )

    ACTOR_STUDENT = "student"
    ACTOR_CURATOR = "curator"
    ACTOR_SYSTEM = "system"
    ACTOR_ROLE_CHOICES = (
        (ACTOR_STUDENT, "Ученик"),
        (ACTOR_CURATOR, "Куратор"),
        (ACTOR_SYSTEM, "Система"),
    )

    owner = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        db_column="owner_id",
        related_name="product_course_events",
    )
    contact_id = models.BigIntegerField(db_index=True)
    product = models.ForeignKey(
        ClientProduct,
        on_delete=models.CASCADE,
        db_column="product_id",
        related_name="course_events",
    )
    course = models.ForeignKey(
        ProductCourse,
        on_delete=models.CASCADE,
        db_column="course_id",
        related_name="events",
    )
    module = models.ForeignKey(
        ProductCourseModule,
        on_delete=models.CASCADE,
        db_column="module_id",
        related_name="events",
    )
    lesson = models.ForeignKey(
        ProductCourseLesson,
        on_delete=models.CASCADE,
        db_column="lesson_id",
        related_name="events",
    )
    progress = models.ForeignKey(
        ProductCourseProgress,
        on_delete=models.SET_NULL,
        db_column="progress_id",
        related_name="events",
        null=True,
        blank=True,
    )
    event_type = models.CharField(max_length=32, choices=EVENT_TYPE_CHOICES)
    actor_role = models.CharField(max_length=16, choices=ACTOR_ROLE_CHOICES)
    actor_user_id = models.BigIntegerField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = 'map"."product_course_events'
        ordering = ("-created_at", "-id")


class ProductCourseComment(models.Model):
    AUTHOR_STUDENT = "student"
    AUTHOR_CURATOR = "curator"
    AUTHOR_SYSTEM = "system"
    AUTHOR_ROLE_CHOICES = (
        (AUTHOR_STUDENT, "Ученик"),
        (AUTHOR_CURATOR, "Куратор"),
        (AUTHOR_SYSTEM, "Система"),
    )

    CHANNEL_COURSES = "courses"
    CHANNEL_TELEGRAM = "telegram"
    CHANNEL_VK = "vk"
    CHANNEL_EMAIL = "email"
    CHANNEL_CHOICES = (
        (CHANNEL_COURSES, "Courses"),
        (CHANNEL_TELEGRAM, "Telegram"),
        (CHANNEL_VK, "VK"),
        (CHANNEL_EMAIL, "Email"),
    )

    owner = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        db_column="owner_id",
        related_name="product_course_comments",
    )
    contact_id = models.BigIntegerField(db_index=True)
    product = models.ForeignKey(
        ClientProduct,
        on_delete=models.CASCADE,
        db_column="product_id",
        related_name="course_comments",
    )
    course = models.ForeignKey(
        ProductCourse,
        on_delete=models.CASCADE,
        db_column="course_id",
        related_name="comments",
    )
    module = models.ForeignKey(
        ProductCourseModule,
        on_delete=models.CASCADE,
        db_column="module_id",
        related_name="comments",
    )
    lesson = models.ForeignKey(
        ProductCourseLesson,
        on_delete=models.CASCADE,
        db_column="lesson_id",
        related_name="comments",
    )
    author_role = models.CharField(max_length=16, choices=AUTHOR_ROLE_CHOICES)
    author_user_id = models.BigIntegerField(blank=True, null=True)
    channel = models.CharField(max_length=16, choices=CHANNEL_CHOICES, default=CHANNEL_COURSES)
    message_text = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = 'map"."product_course_comments'
        ordering = ("created_at", "id")


# ============================================================================
# Mind map (map.mind_*)
# ============================================================================

class MindMap(models.Model):
    owner = models.ForeignKey(Client, on_delete=models.CASCADE, db_column="owner_id", related_name="mind_maps")
    title = models.TextField()
    description = models.TextField(blank=True, null=True)
    type = models.TextField(default="product")
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'map"."mind_maps'

    def __str__(self):
        return self.title


class MindMapMember(models.Model):
    map = models.ForeignKey(MindMap, on_delete=models.CASCADE, db_column="map_id", related_name="members")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column="user_id")
    role = models.TextField()

    class Meta:
        managed = False
        db_table = 'map"."mind_map_members'
        unique_together = ("map", "user")


class MindNode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    map = models.ForeignKey(MindMap, on_delete=models.CASCADE, db_column="map_id", related_name="nodes")
    text = models.TextField()
    color = models.TextField(blank=True, null=True)
    shape = models.TextField(blank=True, null=True)
    meta = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'map"."mind_nodes'

    def __str__(self):
        return self.text


class MindEdge(models.Model):
    id = models.BigAutoField(primary_key=True)
    map = models.ForeignKey(MindMap, on_delete=models.CASCADE, db_column="map_id", related_name="edges")
    from_node = models.ForeignKey(MindNode, on_delete=models.CASCADE, db_column="from_node_id", related_name="edges_from")
    to_node = models.ForeignKey(MindNode, on_delete=models.CASCADE, db_column="to_node_id", related_name="edges_to")
    type = models.TextField(default="default")
    label = models.TextField(blank=True, null=True)
    meta = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'map"."mind_edges'


class MindNodeProperty(models.Model):
    id = models.BigAutoField(primary_key=True)
    node = models.ForeignKey(MindNode, on_delete=models.CASCADE, db_column="node_id", related_name="properties")
    title = models.TextField()
    value = models.TextField()
    delta = models.TextField(blank=True, null=True)
    order_index = models.IntegerField(default=0)
    meta = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'map"."mind_node_properties'


class MindNodePosition(models.Model):
    node = models.OneToOneField(
        MindNode, on_delete=models.CASCADE, db_column="node_id", primary_key=True, related_name="position"
    )
    layout_name = models.TextField(default="default")
    x = models.FloatField()
    y = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'map"."mind_node_positions'


# ============================================================================
# Knowledge base (map.kb_*)
# ============================================================================

class KbFolder(models.Model):
    workspace = models.ForeignKey(Client, on_delete=models.CASCADE, db_column="workspace_id", related_name="kb_folders")
    name = models.TextField()
    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL, db_column="parent_id", related_name="subfolders", null=True, blank=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, db_column="created_by_id",
        related_name="kb_folders_created", null=True, blank=True,
    )
    position = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'map"."kb_folders'

    def __str__(self):
        return self.name


class KbDocument(models.Model):
    DOCUMENT_TYPE_PAGE = "page"
    DOCUMENT_TYPE_PRODUCT = "product"
    DOCUMENT_TYPE_CHOICES = (
        (DOCUMENT_TYPE_PAGE, "Страница"),
        (DOCUMENT_TYPE_PRODUCT, "Продукт"),
    )

    workspace = models.ForeignKey(Client, on_delete=models.CASCADE, db_column="workspace_id", related_name="kb_documents")
    folder = models.ForeignKey(
        KbFolder, on_delete=models.SET_NULL, db_column="folder_id", related_name="documents", null=True, blank=True
    )
    parent_document = models.ForeignKey(
        "self", on_delete=models.SET_NULL, db_column="parent_document_id",
        related_name="child_documents", null=True, blank=True,
    )
    title = models.TextField()
    icon = models.TextField(blank=True, null=True)
    cover_image = models.TextField(blank=True, null=True)
    document_type = models.TextField(default=DOCUMENT_TYPE_PAGE)
    content = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, db_column="created_by_id",
        related_name="kb_documents_created", null=True, blank=True,
    )
    last_edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, db_column="last_edited_by_id",
        related_name="kb_documents_edited", null=True, blank=True,
    )
    is_published = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    is_template = models.BooleanField(default=False)
    index_status = models.TextField(default="pending")
    indexed_at = models.DateTimeField(blank=True, null=True)
    index_error = models.TextField(blank=True, null=True)
    position = models.IntegerField(default=0)
    tags = models.ManyToManyField("KbTag", through="KbDocumentTag", related_name="documents")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'map"."kb_documents'

    def __str__(self):
        return self.title


class KbDocumentVersion(models.Model):
    document = models.ForeignKey(
        KbDocument, on_delete=models.CASCADE, db_column="document_id", related_name="versions"
    )
    title = models.TextField(blank=True, null=True)
    content = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, db_column="created_by_id",
        related_name="kb_document_versions_created", null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    version_number = models.IntegerField(default=1)

    class Meta:
        managed = False
        db_table = 'map"."kb_document_versions'
        unique_together = ("document", "version_number")


class KbComment(models.Model):
    document = models.ForeignKey(
        KbDocument, on_delete=models.CASCADE, db_column="document_id", related_name="comments"
    )
    parent_comment = models.ForeignKey(
        "self", on_delete=models.CASCADE, db_column="parent_comment_id",
        related_name="replies", null=True, blank=True,
    )
    content = models.TextField()
    block_id = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, db_column="created_by_id",
        related_name="kb_comments_created", null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_resolved = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = 'map"."kb_comments'


class KbTag(models.Model):
    workspace = models.ForeignKey(Client, on_delete=models.CASCADE, db_column="workspace_id", related_name="kb_tags")
    name = models.TextField()
    color = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'map"."kb_tags'
        unique_together = ("workspace", "name")

    def __str__(self):
        return self.name


class KbDocumentTag(models.Model):
    document = models.ForeignKey(KbDocument, on_delete=models.CASCADE, db_column="document_id", related_name="document_tags")
    tag = models.ForeignKey(KbTag, on_delete=models.CASCADE, db_column="tag_id", related_name="document_tags")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'map"."kb_document_tags'
        unique_together = ("document", "tag")


class KbDocumentShare(models.Model):
    document = models.ForeignKey(
        KbDocument, on_delete=models.CASCADE, db_column="document_id", related_name="shares"
    )
    share_token = models.TextField(unique=True)
    permission = models.TextField(default="view")
    password = models.TextField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, db_column="created_by_id",
        related_name="kb_shares_created", null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    visit_count = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = 'map"."kb_shares'


# ============================================================================
# Chains / Bot flows (chains.*)
# ============================================================================

class Chain(models.Model):
    tenant = models.ForeignKey(Client, on_delete=models.CASCADE, db_column="tenant_id", related_name="chains")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, default="draft")
    start_node_id = models.BigIntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'chains"."chains'

    def __str__(self):
        return f"{self.tenant_id}:{self.name}"


class ChainNode(models.Model):
    chain = models.ForeignKey(Chain, on_delete=models.CASCADE, db_column="chain_id", related_name="nodes")
    node_type = models.CharField(max_length=20, default="text")
    payload = models.JSONField(default=dict)
    delay_seconds = models.IntegerField(default=0)
    pos_x = models.FloatField(default=0)
    pos_y = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'chains"."chain_nodes'

    def __str__(self):
        return f"{self.chain_id}:{self.node_type}"


class ChainEdge(models.Model):
    chain = models.ForeignKey(Chain, on_delete=models.CASCADE, db_column="chain_id", related_name="edges")
    source_node = models.ForeignKey(ChainNode, on_delete=models.CASCADE, db_column="source_node_id", related_name="edges_from")
    source_port_id = models.CharField(max_length=64, blank=True, null=True)
    target_node = models.ForeignKey(ChainNode, on_delete=models.CASCADE, db_column="target_node_id", related_name="edges_to")
    priority = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'chains"."chain_edges'

    def __str__(self):
        return f"{self.chain_id}:{self.source_node_id}->{self.target_node_id}"


class ChainCondition(models.Model):
    edge = models.ForeignKey(ChainEdge, on_delete=models.CASCADE, db_column="edge_id", related_name="conditions")
    condition_type = models.CharField(max_length=30)
    params = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'chains"."chain_conditions'

    def __str__(self):
        return f"{self.edge_id}:{self.condition_type}"


class ChainSession(models.Model):
    user_id = models.BigIntegerField()
    tenant = models.ForeignKey(Client, on_delete=models.CASCADE, db_column="tenant_id", related_name="chain_sessions")
    chain = models.ForeignKey(Chain, on_delete=models.CASCADE, db_column="chain_id", related_name="sessions")
    current_node = models.ForeignKey(
        ChainNode, on_delete=models.SET_NULL, db_column="current_node_id",
        related_name="sessions", blank=True, null=True,
    )
    status = models.CharField(max_length=20, default="active")
    context = models.JSONField(default=dict)
    started_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'chains"."chain_sessions'

    def __str__(self):
        return f"{self.user_id}:{self.chain_id}:{self.status}"


# ============================================================================
# Quiz builder (chains.quiz_*)
# ============================================================================

class Quiz(models.Model):
    tenant = models.ForeignKey(Client, on_delete=models.CASCADE, db_column="tenant_id", related_name="quizzes")
    title = models.CharField(max_length=255, default="Мой квиз")
    accent_color = models.CharField(max_length=7, default="#5b5ef4")
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'chains"."quizzes'
        ordering = ("-updated_at", "-id")

    def __str__(self):
        return f"{self.tenant_id}:{self.title}"


class QuizScreen(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, db_column="quiz_id", related_name="screens")
    kind = models.CharField(max_length=16)
    position = models.SmallIntegerField(default=0)
    title = models.CharField(max_length=500, default="")
    subtitle = models.CharField(max_length=1000, blank=True, null=True)
    question_type = models.CharField(max_length=16, blank=True, null=True)
    placeholder = models.CharField(max_length=255, blank=True, null=True)
    min_val = models.SmallIntegerField(blank=True, null=True)
    max_val = models.SmallIntegerField(blank=True, null=True)
    max_rating = models.SmallIntegerField(blank=True, null=True)
    is_required = models.BooleanField(default=False)
    is_default_result = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'chains"."quiz_screens'
        ordering = ("position", "id")

    def __str__(self):
        return f"{self.quiz_id}:{self.kind}@{self.position}"


class QuizOption(models.Model):
    screen = models.ForeignKey(QuizScreen, on_delete=models.CASCADE, db_column="screen_id", related_name="options")
    label = models.CharField(max_length=255, default="")
    emoji = models.CharField(max_length=32, default="")
    next_screen = models.ForeignKey(
        QuizScreen,
        on_delete=models.SET_NULL,
        db_column="next_screen_id",
        related_name="incoming_branch_options",
        blank=True,
        null=True,
    )
    next_special = models.CharField(max_length=16, blank=True, null=True)
    position = models.SmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'chains"."quiz_options'
        ordering = ("position", "id")

    def __str__(self):
        return f"{self.screen_id}:{self.position}:{self.label[:24]}"


class QuizResultRule(models.Model):
    screen = models.ForeignKey(QuizScreen, on_delete=models.CASCADE, db_column="screen_id", related_name="result_rules")
    position = models.SmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'chains"."quiz_result_rules'
        ordering = ("position", "id")

    def __str__(self):
        return f"screen={self.screen_id} rule@{self.position}"


class QuizResultCondition(models.Model):
    rule = models.ForeignKey(QuizResultRule, on_delete=models.CASCADE, db_column="rule_id", related_name="conditions")
    screen = models.ForeignKey(QuizScreen, on_delete=models.CASCADE, db_column="screen_id", related_name="result_conditions")
    operator = models.CharField(max_length=16)
    value = models.JSONField(default=list)
    position = models.SmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'chains"."quiz_result_conditions'
        ordering = ("position", "id")

    def __str__(self):
        return f"rule={self.rule_id} cond={self.operator}@{self.position}"


class QuizAnswer(models.Model):
    tenant = models.ForeignKey(Client, on_delete=models.CASCADE, db_column="tenant_id", related_name="quiz_answers")
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, db_column="quiz_id", related_name="answers")
    contact_id = models.BigIntegerField()
    screen = models.ForeignKey(
        QuizScreen,
        on_delete=models.SET_NULL,
        db_column="screen_id",
        related_name="answers",
        blank=True,
        null=True,
    )
    value_text = models.TextField(blank=True, null=True)
    value_number = models.SmallIntegerField(blank=True, null=True)
    value_options = ArrayField(models.BigIntegerField(), blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = 'chains"."quiz_answers'
        ordering = ("created_at", "id")

    def __str__(self):
        return f"quiz={self.quiz_id} contact={self.contact_id} screen={self.screen_id or '-'}"


# ============================================================================
# CRM bindings (map.*)
# ============================================================================

class UserTenantBinding(models.Model):
    PROVIDER_TELEGRAM = "telegram"
    PROVIDER_VK = "vk"
    PROVIDER_CONTACT = "contact"

    tenant = models.ForeignKey(
        Client, on_delete=models.CASCADE, db_column="tenant_id", related_name="telegram_user_bindings"
    )
    provider = models.CharField(max_length=16, default=PROVIDER_TELEGRAM)
    provider_user_id = models.CharField(max_length=255)
    telegram_chat_id = models.BigIntegerField(blank=True, null=True)
    contact_id = models.IntegerField(blank=True, null=True)
    bound_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = 'map"."user_tenant_binding'
        unique_together = (("provider", "provider_user_id", "tenant"),)
        ordering = ("-bound_at", "-id")

    def __str__(self):
        return f"{self.provider}:{self.provider_user_id} -> {self.tenant_id}"


class ContactFact(models.Model):
    contact_id = models.IntegerField(db_index=True)
    tenant_id = models.IntegerField(db_index=True)
    category = models.CharField(max_length=32)
    fact_type = models.CharField(max_length=64)
    fact_value = models.TextField()
    source = models.CharField(max_length=32, default="ai_chat")
    session = models.ForeignKey(
        ChainSession,
        on_delete=models.SET_NULL,
        db_column="session_id",
        related_name="contact_facts",
        blank=True,
        null=True,
    )
    confidence = models.SmallIntegerField(default=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = 'map"."contact_facts'
        ordering = ("-updated_at", "-id")

    def __str__(self):
        return f"contact={self.contact_id} [{self.category}/{self.fact_type}]"


class TelegramTask(models.Model):
    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, db_column="client_id", related_name="telegram_tasks"
    )
    tg_name = models.TextField()
    telegram_user_id = models.BigIntegerField()
    telegram_message_id = models.BigIntegerField(blank=True, null=True)
    message_text = models.TextField()
    received_at = models.DateTimeField()
    rating = models.SmallIntegerField()

    class Meta:
        managed = False
        db_table = 'map"."crm_level'
        ordering = ("-received_at", "-id")

    def __str__(self):
        return f"@{self.tg_name}: {self.message_text[:48]}"


class CRMTask(models.Model):
    level = models.ForeignKey(
        TelegramTask, on_delete=models.SET_NULL, db_column="level_id",
        related_name="crm_tasks", blank=True, null=True,
    )
    source = models.CharField(max_length=32, default="operator")
    contact_id = models.IntegerField(blank=True, null=True)
    goal_id = models.CharField(max_length=128, blank=True, null=True)
    title = models.TextField()
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, default="open")
    priority = models.IntegerField(default=2)
    due_at = models.DateTimeField(blank=True, null=True)
    is_milestone = models.BooleanField(default=False)
    milestone_note = models.TextField(blank=True, null=True)
    done_at = models.DateTimeField(blank=True, null=True)
    created_by = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = 'map"."crm_tasks'
        ordering = ("-updated_at", "-id")

    def __str__(self):
        return self.title


class CRMTaskHistory(models.Model):
    task = models.ForeignKey(
        CRMTask, on_delete=models.CASCADE, db_column="task_id",
        related_name="history_entries",
    )
    note = models.TextField()
    status = models.CharField(max_length=20, blank=True, null=True)
    created_by = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = 'map"."crm_task_history'
        ordering = ("created_at", "id")

    def __str__(self):
        return f"{self.task_id}:{self.created_at}"
