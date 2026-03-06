from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0181_yookassa_payment_provider"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="tbank_connected",
            field=models.BooleanField(
                default=False,
                help_text="True если клиент сохранил ключи T-Bank для приема платежей",
                verbose_name="T-Bank подключен",
            ),
        ),
        migrations.AddField(
            model_name="client",
            name="tbank_secret_key",
            field=models.CharField(
                blank=True,
                help_text="SecretKey из личного кабинета T-Bank",
                max_length=500,
                null=True,
                verbose_name="T-Bank Secret Key",
            ),
        ),
        migrations.AddField(
            model_name="client",
            name="tbank_terminal_key",
            field=models.CharField(
                blank=True,
                help_text="TerminalKey из личного кабинета T-Bank",
                max_length=255,
                null=True,
                verbose_name="T-Bank Terminal Key",
            ),
        ),
        migrations.AddField(
            model_name="client",
            name="tbank_test_mode",
            field=models.BooleanField(
                default=False,
                help_text="Используются тестовые ключи TinkoffBankTest",
                verbose_name="T-Bank тестовый режим",
            ),
        ),
    ]
