from django.db import migrations


def delete_forecasts_without_hourly(apps, schema_editor):
    Forecast = apps.get_model('backoffice', 'Forecast')
    Forecast.objects.filter(hourly=[]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("backoffice", "0088_alter_forecast_hourly"),
    ]

    operations = [
        migrations.RunPython(delete_forecasts_without_hourly, migrations.RunPython.noop),
    ]
