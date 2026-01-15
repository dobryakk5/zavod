from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0098_payment_plan_period"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="plan",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="clients",
                to="core.paymentplan",
            ),
        ),
        migrations.AddField(
            model_name="client",
            name="plan_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
