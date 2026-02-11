import uuid

from django.db import migrations, models
import django.db.models.deletion


def populate_client_uuid(apps, schema_editor):
    Client = apps.get_model("core", "Client")
    db_alias = schema_editor.connection.alias
    qs = Client.objects.using(db_alias).filter(uuid__isnull=True)
    for client in qs.iterator():
        client.uuid = uuid.uuid4()
        client.save(update_fields=["uuid"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0145_chain_chaincondition_chainedge_chainnode_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="uuid",
            field=models.UUIDField(
                editable=False,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="client",
            name="yookassa_oauth_token",
            field=models.CharField(
                blank=True,
                max_length=1000,
                null=True,
                verbose_name="YooKassa OAuth-токен",
                help_text="Заполняется автоматически при подключении через OAuth",
            ),
        ),
        migrations.AddField(
            model_name="client",
            name="yookassa_connected",
            field=models.BooleanField(
                default=False,
                verbose_name="YooKassa подключена",
                help_text="True если клиент успешно подключил свой YooKassa-магазин",
            ),
        ),
        migrations.AddField(
            model_name="client",
            name="yookassa_shop_id",
            field=models.CharField(
                blank=True,
                max_length=100,
                null=True,
                verbose_name="YooKassa Shop ID",
                help_text="ID магазина из личного кабинета YooKassa",
            ),
        ),
        migrations.AddField(
            model_name="client",
            name="yookassa_secret_key",
            field=models.CharField(
                blank=True,
                max_length=500,
                null=True,
                verbose_name="YooKassa Secret Key",
                help_text="Секретный ключ из личного кабинета YooKassa",
            ),
        ),
        migrations.AddField(
            model_name="client",
            name="yookassa_return_url",
            field=models.CharField(
                blank=True,
                max_length=500,
                null=True,
                verbose_name="YooKassa Return URL",
                help_text="Если пусто — генерируется автоматически как /payments/return/<uuid>/",
            ),
        ),
        migrations.CreateModel(
            name="YooKassaPayment",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "payment_id",
                    models.CharField(
                        db_index=True,
                        max_length=100,
                        unique=True,
                        verbose_name="ID платежа в YooKassa",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Ожидает оплаты"),
                            ("succeeded", "Оплачен"),
                            ("canceled", "Отменён"),
                            ("waiting_for_capture", "Ожидает подтверждения"),
                        ],
                        default="pending",
                        max_length=50,
                        verbose_name="Статус",
                    ),
                ),
                (
                    "amount",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=10,
                        null=True,
                        verbose_name="Сумма",
                    ),
                ),
                (
                    "plan_code",
                    models.CharField(
                        blank=True,
                        max_length=100,
                        verbose_name="Код тарифа",
                        help_text="Код тарифа, за который производится оплата",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="yookassa_payments",
                        to="core.client",
                        verbose_name="Клиент",
                    ),
                ),
            ],
            options={
                "verbose_name": "YooKassa Платёж",
                "verbose_name_plural": "YooKassa Платежи",
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddIndex(
            model_name="yookassapayment",
            index=models.Index(fields=["payment_id"], name="yk_payment_id_idx"),
        ),
        migrations.AddIndex(
            model_name="yookassapayment",
            index=models.Index(fields=["client", "-created_at"], name="yk_client_created_idx"),
        ),
        migrations.RunPython(populate_client_uuid, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="client",
            name="uuid",
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                unique=True,
                verbose_name="UUID клиента",
            ),
        ),
    ]
