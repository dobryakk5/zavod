from django.db import migrations, models


def seed_payment_plans(apps, schema_editor):
    PaymentPlan = apps.get_model("core", "PaymentPlan")
    plans = [
        {
            "code": "starter",
            "name": "Starter",
            "amount": "4900.00",
            "currency": "RUB",
            "period": "month",
            "description": "Базовый тариф\nAI-контент\nЗапуск гипотез",
            "sort_order": 1,
        },
        {
            "code": "growth",
            "name": "Growth",
            "amount": "9900.00",
            "currency": "RUB",
            "period": "month",
            "description": "Для роста\nКонтент-пайплайн\nАвтопостинг",
            "sort_order": 2,
        },
        {
            "code": "scale",
            "name": "Scale",
            "amount": "19900.00",
            "currency": "RUB",
            "period": "month",
            "description": "Для команд\nИнтеграции\nКастом AI",
            "sort_order": 3,
        },
    ]

    for plan_data in plans:
        PaymentPlan.objects.update_or_create(
            code=plan_data["code"],
            defaults=plan_data,
        )


def unseed_payment_plans(apps, schema_editor):
    PaymentPlan = apps.get_model("core", "PaymentPlan")
    PaymentPlan.objects.filter(code__in=["starter", "growth", "scale"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0097_payment_plan"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentplan",
            name="period",
            field=models.CharField(
                choices=[("week", "Неделя"), ("month", "Месяц"), ("year", "Год")],
                default="month",
                max_length=8,
            ),
        ),
        migrations.RunPython(seed_payment_plans, unseed_payment_plans),
    ]
