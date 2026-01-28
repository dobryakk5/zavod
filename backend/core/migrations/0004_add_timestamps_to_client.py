# Manually created migration to add timestamp fields to Client model without creating them in DB
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_add_timestamps_to_client'),
    ]

    operations = [
        # These fields were already created in migration 0003, now we're just adding them to the model
        # We use state operations to update the model state without affecting the database
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='client',
                    name='created_at',
                    field=models.DateTimeField(auto_now_add=True),
                ),
                migrations.AddField(
                    model_name='client',
                    name='updated_at',
                    field=models.DateTimeField(auto_now=True),
                ),
            ],
            database_operations=[]
        ),
    ]