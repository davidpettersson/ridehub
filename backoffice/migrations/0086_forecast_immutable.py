from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backoffice', '0085_forecast_rename_fields'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='forecast',
            name='unique_forecast_location_window',
        ),
        migrations.RenameField(
            model_name='forecast',
            old_name='updated_at',
            new_name='prepared_at',
        ),
        migrations.AlterField(
            model_name='forecast',
            name='prepared_at',
            field=models.DateTimeField(
                auto_now_add=True,
                help_text='When this forecast was fetched from the weather provider. Forecasts are immutable; newer fetches create new records.',
            ),
        ),
        migrations.AlterField(
            model_name='forecast',
            name='conditions',
            field=models.CharField(
                help_text='Comma-separated weather conditions occurring during the forecast window, most prevalent first.',
                max_length=32,
            ),
        ),
    ]
