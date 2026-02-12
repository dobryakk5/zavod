"""
Django модели для CRM системы (схема map)
Работает с существующими таблицами map.contacts, map.crm_payments и т.д.
"""
from decimal import Decimal

from django.db import models
from django.core.validators import MinValueValidator


class MapContact(models.Model):
    """
    Клиент тенанта (map.contacts)
    Конечные клиенты бизнеса
    """
    name = models.CharField(max_length=200, verbose_name="Имя клиента")
    email = models.EmailField(blank=True, verbose_name="Email")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Телефон")
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
        ]

    def __str__(self):
        return self.name


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
    product_id = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="ID продукта",
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
            models.Index(fields=["transaction_id"]),
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
