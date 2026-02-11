from django.db import models


class PaymentPlan(models.Model):
    PERIOD_WEEK = "week"
    PERIOD_MONTH = "month"
    PERIOD_YEAR = "year"
    PERIOD_CHOICES = [
        (PERIOD_WEEK, "Неделя"),
        (PERIOD_MONTH, "Месяц"),
        (PERIOD_YEAR, "Год"),
    ]

    code = models.SlugField(unique=True)
    name = models.CharField(max_length=150)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="RUB")
    period = models.CharField(max_length=8, choices=PERIOD_CHOICES, default=PERIOD_MONTH)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Payment Plan"
        verbose_name_plural = "Payment Plans"
        ordering = ("sort_order", "name")

    def __str__(self):
        return f"{self.name} ({self.amount} {self.currency})"


class YooKassaPayment(models.Model):
    """Хранит связь payment_id → Client для вебхуков YooKassa."""

    STATUS_PENDING = "pending"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_CANCELED = "canceled"
    STATUS_WAITING = "waiting_for_capture"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Ожидает оплаты"),
        (STATUS_SUCCEEDED, "Оплачен"),
        (STATUS_CANCELED, "Отменён"),
        (STATUS_WAITING, "Ожидает подтверждения"),
    ]

    payment_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        verbose_name="ID платежа в YooKassa",
    )
    client = models.ForeignKey(
        "Client",
        on_delete=models.CASCADE,
        related_name="yookassa_payments",
        verbose_name="Клиент",
    )
    status = models.CharField(
        max_length=50,
        default=STATUS_PENDING,
        choices=STATUS_CHOICES,
        verbose_name="Статус",
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Сумма",
    )
    plan_code = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Код тарифа",
        help_text="Код тарифа, за который производится оплата",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "YooKassa Платёж"
        verbose_name_plural = "YooKassa Платежи"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["payment_id"], name="yk_payment_id_idx"),
            models.Index(fields=["client", "-created_at"], name="yk_client_created_idx"),
        ]

    def __str__(self):
        return f"{self.payment_id} — {self.client} — {self.status}"
