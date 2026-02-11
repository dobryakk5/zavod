from django.db import models

from .client import Client


class ClientCategory(models.Model):
    """Категории клиентов."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, help_text="HEX цвет для UI")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "crm_client_categories"

    def __str__(self) -> str:
        return self.name


class CRMClient(models.Model):
    """Клиент в CRM-системе."""

    STATUS_CHOICES = [
        ("active", "Активный"),
        ("inactive", "Неактивный"),
        ("archived", "В архиве"),
    ]

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True)
    category = models.ForeignKey(ClientCategory, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    photo_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Связь с клиентом zavod
    zavod_client = models.ForeignKey(Client, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        db_table = "crm_clients"

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}"


class EventType(models.Model):
    """Типы событий."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    duration_minutes = models.IntegerField(default=60)
    color = models.CharField(max_length=7, help_text="HEX цвет для UI")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "crm_event_types"

    def __str__(self) -> str:
        return self.name


class Event(models.Model):
    """События (встречи, консультации и т.д.)."""

    STATUS_CHOICES = [
        ("scheduled", "Запланировано"),
        ("completed", "Завершено"),
        ("cancelled", "Отменено"),
        ("no_show", "Не явился"),
    ]

    client = models.ForeignKey(CRMClient, on_delete=models.CASCADE)
    event_type = models.ForeignKey(EventType, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    location = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="scheduled")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "crm_events"
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_time__gt=models.F("start_time")),
                name="check_event_time",
            )
        ]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs) -> None:
        if self.end_time <= self.start_time:
            raise ValueError("Время окончания должно быть больше времени начала")
        super().save(*args, **kwargs)


class Payment(models.Model):
    """Платежи."""

    PAYMENT_STATUS_CHOICES = [
        ("pending", "В ожидании"),
        ("paid", "Оплачено"),
        ("failed", "Ошибка"),
        ("refunded", "Возврат"),
    ]

    CURRENCY_CHOICES = [
        ("RUB", "Рубль"),
        ("USD", "Доллар"),
        ("EUR", "Евро"),
    ]

    client = models.ForeignKey(CRMClient, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Сумма платежа")
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="RUB")
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default="pending")
    payment_method = models.CharField(max_length=50, blank=True)
    transaction_id = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "crm_payments"
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gt=0),
                name="check_positive_amount",
            )
        ]

    def __str__(self) -> str:
        return f"{self.amount} {self.currency} - {self.status}"


class Note(models.Model):
    """Заметки о клиентах."""

    client = models.ForeignKey(CRMClient, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, blank=True)
    content = models.TextField()
    is_important = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "crm_notes"

    def __str__(self) -> str:
        return self.title or f"Заметка от {self.created_at.date()}"
