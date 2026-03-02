"""
Django модели для CRM системы (схема map)
Работает с существующими таблицами map.contacts, map.crm_payments и т.д.
"""
from decimal import Decimal

from django.db import models
from django.core.validators import MinValueValidator

from .client import Client


class MapContact(models.Model):
    """
    Клиент тенанта (map.contacts)
    Конечные клиенты бизнеса
    """
    name = models.CharField(max_length=200, verbose_name="Имя клиента")
    email = models.EmailField(blank=True, verbose_name="Email")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Телефон")
    source = models.CharField(max_length=255, blank=True, verbose_name="Источник")
    deal_stage = models.CharField(max_length=32, blank=True, default="", verbose_name="Стадия сделки")
    deal_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Сумма сделки",
    )
    deal_loss_reason_code = models.CharField(max_length=64, blank=True, default="", verbose_name="Код причины потери")
    deal_loss_reason_text = models.TextField(blank=True, verbose_name="Комментарий причины потери")
    deal_lost_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата потери сделки")
    category_id = models.IntegerField(null=True, blank=True, verbose_name="ID категории")
    status = models.CharField(
        max_length=20,
        default="active",
        choices=[
            ("active", "Активный"),
            ("inactive", "Неактивный"),
            ("archived", "В архиве"),
        ],
        verbose_name="Статус",
    )
    photo_url = models.URLField(blank=True, verbose_name="URL фото")
    notes = models.TextField(blank=True, verbose_name="Заметки")
    parent_id = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="ID родительского клиента",
    )
    tg_user_id = models.BigIntegerField(null=True, blank=True, verbose_name="Telegram user ID")
    tg_username = models.TextField(blank=True, verbose_name="Telegram username")
    tg_connected_at = models.DateField(null=True, blank=True, verbose_name="Дата привязки Telegram")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        db_table = '"map"."contacts"'
        managed = False
        ordering = ["name"]
        verbose_name = "Контакт (map)"
        verbose_name_plural = "Контакты (map)"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["email"]),
            models.Index(fields=["parent_id"]),
            models.Index(fields=["deal_stage"]),
            models.Index(fields=["deal_loss_reason_code"]),
        ]

    def __str__(self):
        return self.name


class MapCRMDeal(models.Model):
    """
    Сделка клиента (map.crm_deals)
    Может иметь несколько платежей.
    """
    STAGE_NEW_LEAD = "new_lead"
    STAGE_INTEREST = "interest"
    STAGE_CALL = "call"
    STAGE_PAYMENT_EXPECTED = "payment_expected"
    STAGE_PAID = "paid"
    STAGE_LOST = "lost"

    contact = models.ForeignKey(
        MapContact,
        on_delete=models.CASCADE,
        related_name="deals",
        db_column="contact_id",
        verbose_name="Клиент",
    )
    product_id = models.IntegerField(
        verbose_name="ID продукта",
    )
    stage = models.CharField(
        max_length=32,
        default=STAGE_NEW_LEAD,
        choices=[
            (STAGE_NEW_LEAD, "Новый лид"),
            (STAGE_INTEREST, "Интерес"),
            (STAGE_CALL, "Созвон"),
            (STAGE_PAYMENT_EXPECTED, "Оплата ожидается"),
            (STAGE_PAID, "Оплачено"),
            (STAGE_LOST, "Срыв"),
        ],
        verbose_name="Стадия сделки",
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Сумма сделки",
    )
    currency = models.CharField(
        max_length=3,
        default="RUB",
        choices=[
            ("RUB", "Рубль"),
            ("USD", "Доллар"),
            ("EUR", "Евро"),
        ],
        verbose_name="Валюта",
    )
    description = models.TextField(blank=True, verbose_name="Описание")
    lost_reason_code = models.CharField(max_length=64, blank=True, default="", verbose_name="Код причины срыва")
    lost_reason_text = models.TextField(blank=True, verbose_name="Комментарий причины срыва")
    lost_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата срыва")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        db_table = '"map"."crm_deals"'
        managed = False
        ordering = ["-created_at"]
        verbose_name = "Сделка (map)"
        verbose_name_plural = "Сделки (map)"
        indexes = [
            models.Index(fields=["contact", "stage"]),
            models.Index(fields=["stage", "created_at"]),
            models.Index(fields=["product_id"]),
        ]

    def __str__(self):
        return f"Сделка #{self.id} - {self.contact.name}"


class MapCRMPayment(models.Model):
    """
    Платёж от клиента (map.crm_payments)
    """
    contact = models.ForeignKey(
        MapContact,
        on_delete=models.CASCADE,
        related_name="payments",
        db_column="contact_id",
        verbose_name="Клиент",
    )
    deal = models.ForeignKey(
        MapCRMDeal,
        on_delete=models.SET_NULL,
        related_name="payments",
        db_column="deal_id",
        null=True,
        blank=True,
        verbose_name="Сделка",
    )
    product_id = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="ID продукта",
    )
    event_id = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="ID встречи",
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name="Сумма",
    )
    currency = models.CharField(
        max_length=3,
        default="RUB",
        choices=[
            ("RUB", "Рубль"),
            ("USD", "Доллар"),
            ("EUR", "Евро"),
        ],
        verbose_name="Валюта",
    )
    status = models.CharField(
        max_length=20,
        default="pending",
        choices=[
            ("pending", "В ожидании"),
            ("paid", "Оплачено"),
            ("failed", "Ошибка"),
            ("refunded", "Возврат"),
        ],
        verbose_name="Статус",
    )

    payment_method = models.CharField(max_length=100, blank=True, verbose_name="Способ оплаты")
    transaction_id = models.CharField(max_length=200, blank=True, verbose_name="ID транзакции")
    description = models.TextField(blank=True, verbose_name="Описание")

    planned_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Планируемая дата оплаты",
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата оплаты",
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        db_table = '"map"."crm_payments"'
        managed = False
        ordering = ["-created_at"]
        verbose_name = "Платёж (map)"
        verbose_name_plural = "Платежи (map)"
        indexes = [
            models.Index(fields=["contact", "status"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["contact", "paid_at"]),
            models.Index(fields=["deal"]),
            models.Index(fields=["transaction_id"]),
            models.Index(fields=["event_id"]),
        ]

    def __str__(self):
        return f"{self.amount} {self.currency} - {self.contact.name}"

    def save(self, *args, **kwargs):
        from django.utils import timezone

        if self.status == "paid" and not self.paid_at:
            self.paid_at = timezone.now()
        super().save(*args, **kwargs)


class MapCRMTag(models.Model):
    """
    Тег для классификации клиентов (map.crm_tags)
    """
    type = models.CharField(
        max_length=20,
        choices=[
            ("goal", "Цель"),
            ("pain", "Боль"),
            ("experience", "Опыт"),
        ],
        verbose_name="Тип",
    )
    value = models.CharField(max_length=100, verbose_name="Значение")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        db_table = '"map"."crm_tags"'
        managed = False
        unique_together = [["type", "value"]]
        ordering = ["type", "value"]
        verbose_name = "Тег (map)"
        verbose_name_plural = "Теги (map)"

    def __str__(self):
        return f"{self.get_type_display()}: {self.value}"


class MapContactTag(models.Model):
    """
    Связь контакта и тега с дополнительным описанием (map.contact_tags)
    """
    contact = models.ForeignKey(
        MapContact,
        on_delete=models.CASCADE,
        related_name="contact_tags",
        db_column="contact_id",
        verbose_name="Клиент",
    )
    tag = models.ForeignKey(
        MapCRMTag,
        on_delete=models.CASCADE,
        related_name="contact_tags",
        db_column="tag_id",
        verbose_name="Тег",
    )
    description = models.TextField(
        blank=True,
        verbose_name="Дополнительное описание",
    )

    class Meta:
        db_table = '"map"."contact_tags"'
        managed = False
        unique_together = [["contact", "tag"]]
        verbose_name = "Тег контакта (map)"
        verbose_name_plural = "Теги контактов (map)"

    def __str__(self):
        return f"{self.contact.name} - {self.tag}"


class MapCRMCategory(models.Model):
    """
    Категория клиентов (map.crm_categories)
    """
    name = models.CharField(max_length=100, verbose_name="Название")
    description = models.TextField(blank=True, verbose_name="Описание")
    color = models.CharField(
        max_length=7,
        default="#4A90E2",
        verbose_name="Цвет (HEX)",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        db_table = '"map"."crm_categories"'
        managed = False
        ordering = ["name"]
        verbose_name = "Категория (map)"
        verbose_name_plural = "Категории (map)"

    def __str__(self):
        return self.name


class MapCRMEventType(models.Model):
    """
    Тип встречи (map.crm_event_types)
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Название")
    description = models.TextField(blank=True, verbose_name="Описание")
    duration_minutes = models.IntegerField(default=60, verbose_name="Длительность, минут")
    color = models.CharField(max_length=7, default="#4A90E2", verbose_name="Цвет (HEX)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        db_table = '"map"."crm_event_types"'
        managed = False
        ordering = ["name"]
        verbose_name = "Тип встречи (map)"
        verbose_name_plural = "Типы встреч (map)"

    def __str__(self):
        return self.name


class MapCRMEvent(models.Model):
    """
    Встреча/событие клиента (map.crm_events)
    """
    contact = models.ForeignKey(
        MapContact,
        on_delete=models.CASCADE,
        db_column="contact_id",
        related_name="events",
        verbose_name="Контакт",
    )
    event_type = models.ForeignKey(
        MapCRMEventType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="event_type_id",
        related_name="events",
        verbose_name="Тип встречи",
    )
    title = models.CharField(max_length=255, verbose_name="Название")
    description = models.TextField(blank=True, verbose_name="Описание")
    start_time = models.DateTimeField(verbose_name="Начало")
    end_time = models.DateTimeField(verbose_name="Окончание")
    location = models.CharField(max_length=255, blank=True, verbose_name="Место")
    status = models.CharField(
        max_length=20,
        default="scheduled",
        choices=[
            ("scheduled", "Запланировано"),
            ("completed", "Завершено"),
            ("cancelled", "Отменено"),
            ("no_show", "Не пришел"),
        ],
        verbose_name="Статус",
    )
    notes = models.TextField(blank=True, verbose_name="Заметки")
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name="Стоимость",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        db_table = '"map"."crm_events"'
        managed = False
        ordering = ["-start_time"]
        verbose_name = "Встреча (map)"
        verbose_name_plural = "Встречи (map)"
        indexes = [
            models.Index(fields=["contact", "start_time"]),
            models.Index(fields=["event_type"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.start_time})"


class MapAvailabilityEvent(models.Model):
    """
    Доступные слоты календаря тенанта (map.events)
    """
    tenant = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        db_column="tenant_id",
        related_name="availability_events",
        verbose_name="Тенант",
    )
    start_time = models.DateTimeField(verbose_name="Начало")
    duration_minutes = models.SmallIntegerField(default=60, verbose_name="Длительность, минут")
    repeat_type = models.SmallIntegerField(
        default=0,
        choices=[
            (0, "Не повторять"),
            (1, "Еженедельно"),
            (2, "Каждые 2 недели"),
            (3, "Ежемесячно"),
        ],
        verbose_name="Тип повторения",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        db_table = '"map"."events"'
        managed = False
        ordering = ["-start_time"]
        verbose_name = "Слот доступности (map)"
        verbose_name_plural = "Слоты доступности (map)"
        indexes = [
            models.Index(fields=["tenant", "start_time"]),
            models.Index(fields=["tenant", "repeat_type"]),
        ]

    def __str__(self):
        return f"{self.tenant_id}: {self.start_time}"


class MapCRMNote(models.Model):
    """
    Заметка по контакту (map.crm_notes)
    """
    contact = models.ForeignKey(
        MapContact,
        on_delete=models.CASCADE,
        db_column="contact_id",
        related_name="notes_items",
        verbose_name="Контакт",
    )
    title = models.CharField(max_length=255, verbose_name="Заголовок")
    content = models.TextField(verbose_name="Содержимое")
    is_important = models.BooleanField(default=False, verbose_name="Важная")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        db_table = '"map"."crm_notes"'
        managed = False
        ordering = ["-created_at"]
        verbose_name = "Заметка (map)"
        verbose_name_plural = "Заметки (map)"
        indexes = [
            models.Index(fields=["contact", "is_important"]),
        ]

    def __str__(self):
        return self.title
