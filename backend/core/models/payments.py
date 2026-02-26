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


class ContactProductPurchase(models.Model):
    """
    Право доступа контакта к цифровому продукту (список покупок на /c/[client_id]).

    Храним entitlement по связке client + contact + product, а не историю всех платежей.
    При повторной покупке обновляем запись.
    """

    client = models.ForeignKey(
        "Client",
        on_delete=models.CASCADE,
        related_name="contact_product_purchases",
        verbose_name="Клиент",
    )
    contact_id = models.BigIntegerField(db_index=True, verbose_name="ID контакта (map.contact)")
    product_id = models.BigIntegerField(db_index=True, verbose_name="ID продукта (map.products)")
    product_name = models.CharField(max_length=255, blank=True, default="", verbose_name="Название продукта")
    last_payment = models.ForeignKey(
        "YooKassaPayment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="contact_product_purchases",
        verbose_name="Последний платеж YooKassa",
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Сумма покупки",
    )
    currency = models.CharField(max_length=3, default="RUB", verbose_name="Валюта")
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата оплаты")
    service_package_mode = models.CharField(
        max_length=16,
        blank=True,
        default="",
        verbose_name="Режим сервисного пакета",
        help_text="count | minutes; пусто если продукт не является пакетом услуг",
    )
    service_package_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Название пакета услуг",
    )
    service_package_total_units = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Всего единиц в пакете услуг",
    )
    service_package_used_units = models.PositiveIntegerField(
        default=0,
        verbose_name="Израсходовано единиц в пакете услуг",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Покупка цифрового продукта контактом"
        verbose_name_plural = "Покупки цифровых продуктов контактами"
        ordering = ("-paid_at", "-updated_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("client", "contact_id", "product_id"),
                name="uniq_contact_product_purchase",
            ),
        ]
        indexes = [
            models.Index(fields=("client", "contact_id"), name="idx_cpp_client_contact"),
            models.Index(fields=("client", "product_id"), name="idx_cpp_client_product"),
        ]

    def __str__(self):
        return f"client={self.client_id} contact={self.contact_id} product={self.product_id}"


class ContactProductServiceUsage(models.Model):
    """
    Идемпотентное списание пакета услуг по встречам CRM.

    На одну CRM-встречу приходится максимум одна запись списания.
    Это позволяет безопасно пересчитывать списание при изменении статуса/времени встречи.
    """

    MODE_COUNT = "count"
    MODE_MINUTES = "minutes"
    MODE_CHOICES = [
        (MODE_COUNT, "По количеству встреч"),
        (MODE_MINUTES, "По минутам"),
    ]

    purchase = models.ForeignKey(
        ContactProductPurchase,
        on_delete=models.CASCADE,
        related_name="service_usages",
        verbose_name="Покупка пакета",
    )
    client = models.ForeignKey(
        "Client",
        on_delete=models.CASCADE,
        related_name="contact_product_service_usages",
        verbose_name="Клиент",
    )
    contact_id = models.BigIntegerField(db_index=True, verbose_name="ID контакта (map.contact)")
    event_id = models.BigIntegerField(db_index=True, unique=True, verbose_name="ID встречи (map.crm_events)")
    mode = models.CharField(max_length=16, choices=MODE_CHOICES, verbose_name="Режим списания")
    units = models.PositiveIntegerField(verbose_name="Списанные единицы (встречи/минуты)")
    event_started_at = models.DateTimeField(null=True, blank=True, verbose_name="Начало встречи")
    event_ended_at = models.DateTimeField(null=True, blank=True, verbose_name="Окончание встречи")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Списание пакета услуг по встрече"
        verbose_name_plural = "Списания пакетов услуг по встречам"
        ordering = ("-updated_at", "-id")
        indexes = [
            models.Index(fields=("client", "contact_id"), name="idx_cpsu_client_contact"),
            models.Index(fields=("purchase",), name="idx_cpsu_purchase"),
        ]

    def __str__(self) -> str:
        return f"purchase={self.purchase_id} event={self.event_id} units={self.units}"
