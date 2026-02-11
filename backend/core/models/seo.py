from typing import Dict, List

from django.db import models

from .client import Client
from .story import Topic


class SEOKeywordSet(models.Model):
    """SEO подборка ключевых фраз для клиента."""

    GROUP_TYPE_CHOICES = [
        ("seo_pains", "SEO Pains"),
        ("seo_desires", "SEO Desires"),
        ("seo_objections", "SEO Objections"),
        ("seo_avatar", "SEO Avatar"),
        ("seo_keywords", "SEO Keywords"),
    ]

    STATUS_CHOICES = (
        ("pending", "Ожидает генерации"),
        ("generating", "Генерируется"),
        ("completed", "Завершено"),
        ("failed", "Ошибка"),
    )

    topic = models.ForeignKey(
        Topic,
        on_delete=models.SET_NULL,
        related_name="seo_keyword_sets",
        null=True,
        blank=True,
        help_text="(опционально) Историческая связь с конкретной темой",
    )
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="seo_keyword_sets")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    keyword_groups = models.JSONField(
        default=dict,
        blank=True,
        help_text="Группы SEO-фраз: commercial, general, informational и т.д.",
    )
    # Устаревшее поле, оставлено для совместимости (будет удалено после миграции)
    keywords_text = models.TextField(
        blank=True,
        help_text="[DEPRECATED] Список ключевых SEO-фраз, сгенерированных AI",
    )
    group_type = models.CharField(
        max_length=32,
        choices=GROUP_TYPE_CHOICES,
        blank=True,
        default="",
        help_text="Тип SEO-группы (по умолчанию пусто для старых записей)",
    )
    keywords_list = models.JSONField(
        default=list,
        blank=True,
        help_text="Список ключевых фраз для группы (используется для новых генераций)",
    )
    ai_model = models.CharField(max_length=100, blank=True)
    prompt_used = models.TextField(blank=True)
    error_log = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "SEO Keyword Set"
        verbose_name_plural = "SEO Keyword Sets"

    def __str__(self):
        topic_part = f" → {self.topic.name}" if self.topic else ""
        group_part = f" [{self.group_type}]" if self.group_type else ""
        return f"[{self.client.slug}] SEO{topic_part}{group_part} ({self.status})"

    def get_keyword_groups_for_generation(self) -> Dict[str, List[str]]:
        def _clean(items) -> List[str]:
            return [kw.strip() for kw in items if isinstance(kw, str) and kw.strip()] \
                if isinstance(items, list) else []

        groups: Dict[str, List[str]] = {}
        primary_group_name = self.group_type or "seo_keywords"
        primary_keywords = _clean(self.keywords_list)
        if primary_keywords:
            groups[primary_group_name] = primary_keywords
        if isinstance(self.keyword_groups, dict):
            for group_name, keywords in self.keyword_groups.items():
                cleaned = _clean(keywords)
                if cleaned and group_name not in groups:
                    groups[str(group_name)] = cleaned
        return groups

    def get_flat_keywords(self) -> List[str]:
        return [kw for kws in self.get_keyword_groups_for_generation().values() for kw in kws]


class ProjectSemanticSet(models.Model):
    """Семантика проекта, сгенерированная на основе книг экспертов."""

    SOURCE_EXPERT_BOOKS = "expert_books"
    SOURCE_CHOICES = ((SOURCE_EXPERT_BOOKS, "Expert books"),)

    STATUS_CHOICES = (
        ("pending", "Ожидает генерации"),
        ("generating", "Генерируется"),
        ("completed", "Завершено"),
        ("failed", "Ошибка"),
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="semantic_sets")
    source = models.CharField(max_length=32, choices=SOURCE_CHOICES, default=SOURCE_EXPERT_BOOKS)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    books_text = models.TextField(blank=True, help_text="Книги экспертов, использованные для генерации")
    keyword_groups = models.JSONField(default=dict, blank=True)
    keywords_list = models.JSONField(default=list, blank=True)
    ai_model = models.CharField(max_length=100, blank=True)
    prompt_used = models.TextField(blank=True)
    error_log = models.TextField(blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Project Semantic Set"
        verbose_name_plural = "Project Semantic Sets"

    def __str__(self):
        return f"[{self.client.slug}] Semantics ({self.status})"

    def get_flat_keywords(self) -> List[str]:
        seen: set = set()
        result: List[str] = []
        source = self.keywords_list or []
        if not source and isinstance(self.keyword_groups, dict):
            for kws in self.keyword_groups.values():
                source += kws if isinstance(kws, list) else []
        for kw in source:
            if not isinstance(kw, str):
                continue
            value = kw.strip()
            if value and value.lower() not in seen:
                seen.add(value.lower())
                result.append(value)
        return result


class SemanticGroup(models.Model):
    """Смысловые группы (карта ниши)."""

    SCOPE_CHOICES = (("narrow", "Narrow"), ("normal", "Normal"), ("wide", "Wide"))
    STATUS_CHOICES = (("draft", "Draft"), ("approved", "Approved"), ("archived", "Archived"))
    SOURCE_CHOICES = (("ai", "AI"), ("manual", "Manual"))

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="semantic_groups")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    source_books = models.JSONField(default=list, blank=True)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, related_name="children", null=True, blank=True)
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, blank=True, default="normal")
    expected_clusters = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="ai")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "semantic_groups"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["client", "status"], name="semgrp_client_status_idx"),
            models.Index(fields=["client", "created_at"], name="semgrp_client_created_idx"),
        ]
        verbose_name = "Semantic Group"
        verbose_name_plural = "Semantic Groups"

    def __str__(self):
        return f"[{self.client.slug}] {self.name}"


class SemanticCluster(models.Model):
    """SEO-кластеры (интент = страница)."""

    INTENT_CHOICES = (
        ("info", "Info"),
        ("commercial", "Commercial"),
        ("navigational", "Navigational"),
        ("brand", "Brand"),
    )
    STATUS_CHOICES = (
        ("planned", "Planned"),
        ("in_progress", "In progress"),
        ("published", "Published"),
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="semantic_clusters")
    semantic_group = models.ForeignKey(SemanticGroup, on_delete=models.CASCADE, related_name="clusters")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    main_keyword = models.CharField(max_length=255, blank=True)
    intent = models.CharField(max_length=20, choices=INTENT_CHOICES, blank=True)
    user_goal = models.TextField(blank=True)
    cta = models.CharField(max_length=255, blank=True)
    priority = models.PositiveSmallIntegerField(null=True, blank=True)
    page_type = models.CharField(max_length=50, blank=True)
    url = models.URLField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planned")
    phrases = models.ManyToManyField(
        "SemanticPhrase", through="ClusterPhrase", related_name="clusters", blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "clusters"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["client", "semantic_group"], name="semclust_client_group_idx"),
            models.Index(fields=["client", "status"], name="semclust_client_status_idx"),
            models.Index(fields=["client", "intent"], name="semclust_client_intent_idx"),
        ]
        verbose_name = "Semantic Cluster"
        verbose_name_plural = "Semantic Clusters"

    def __str__(self):
        return f"[{self.client.slug}] {self.name}"


class WordstatPhrase(models.Model):
    """Нормализованные Wordstat-фразы (общие для всех клиентов)."""

    phrase = models.TextField(unique=True)
    frequency = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "wordstat_phrases"
        ordering = ("phrase", "id")
        verbose_name = "Wordstat Phrase"
        verbose_name_plural = "Wordstat Phrases"

    def __str__(self):
        return self.phrase


class SemanticPhrase(models.Model):
    """Ключевые фразы и LSI."""

    TYPE_CHOICES = (
        ("key", "Key"), ("lsi", "LSI"), ("wordstat", "Wordstat"), ("association", "Association"),
    )
    SOURCE_CHOICES = (
        ("ai", "AI"), ("wordstat", "Wordstat"), ("gsc", "GSC"), ("manual", "Manual"), ("favorite", "Favorite"),
    )
    INTENT_CHOICES = SemanticCluster.INTENT_CHOICES

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="semantic_phrases")
    phrase = models.ForeignKey(
        WordstatPhrase, on_delete=models.CASCADE, related_name="semantic_phrases", null=True, blank=True
    )
    raw_phrase = models.TextField(blank=True, null=True)
    normalized_phrase = models.TextField(blank=True, null=True)
    comment = models.TextField(blank=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="key")
    intent = models.CharField(max_length=20, choices=INTENT_CHOICES, blank=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="ai")
    competition = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "phrases"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["client", "source"], name="semphr_client_source_idx"),
            models.Index(fields=["client", "phrase"], name="semphr_client_phrase_idx"),
        ]
        verbose_name = "Semantic Phrase"
        verbose_name_plural = "Semantic Phrases"

    def __str__(self):
        text = self.normalized_phrase or self.raw_phrase or (self.phrase.phrase if self.phrase_id else "")
        return f"[{self.client.slug}] {text[:80]}"


class ClusterPhrase(models.Model):
    """Связь кластеров с фразами (many-to-many через промежуточную таблицу)."""

    ROLE_CHOICES = (("main", "Main"), ("support", "Support"), ("lsi", "LSI"))
    ADDED_BY_CHOICES = (("ai", "AI"), ("manual", "Manual"))

    cluster = models.ForeignKey(SemanticCluster, on_delete=models.CASCADE, related_name="cluster_phrases")
    phrase = models.ForeignKey(SemanticPhrase, on_delete=models.CASCADE, related_name="cluster_phrases")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="support")
    weight = models.PositiveSmallIntegerField(null=True, blank=True)
    added_by = models.CharField(max_length=20, choices=ADDED_BY_CHOICES, default="ai")

    class Meta:
        db_table = "cluster_phrases"
        unique_together = ("cluster", "phrase")
        indexes = [
            models.Index(fields=["cluster", "role"], name="clphr_cluster_role_idx"),
            models.Index(fields=["phrase"], name="clphr_phrase_idx"),
        ]
        verbose_name = "Cluster Phrase"
        verbose_name_plural = "Cluster Phrases"

    def __str__(self):
        return f"{self.cluster_id} -> {self.phrase_id}"
