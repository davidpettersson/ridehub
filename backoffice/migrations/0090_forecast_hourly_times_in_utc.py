from datetime import datetime, timezone as datetime_timezone
from zoneinfo import ZoneInfo

from django.db import migrations

PROVIDER_TIMEZONE = ZoneInfo('America/Toronto')


def hourly_times_to_utc(apps, schema_editor):
    Forecast = apps.get_model('backoffice', 'Forecast')

    for forecast in Forecast.objects.exclude(hourly=[]).iterator():
        converted = []
        changed = False
        for entry in forecast.hourly:
            time = datetime.fromisoformat(entry['time'])
            if time.tzinfo is None:
                time = time.replace(tzinfo=PROVIDER_TIMEZONE).astimezone(datetime_timezone.utc)
                changed = True
            converted.append({**entry, 'time': time.isoformat()})
        if changed:
            forecast.hourly = converted
            forecast.save(update_fields=['hourly'])


def hourly_times_to_provider_local(apps, schema_editor):
    Forecast = apps.get_model('backoffice', 'Forecast')

    for forecast in Forecast.objects.exclude(hourly=[]).iterator():
        converted = []
        changed = False
        for entry in forecast.hourly:
            time = datetime.fromisoformat(entry['time'])
            if time.tzinfo is not None:
                time = time.astimezone(PROVIDER_TIMEZONE).replace(tzinfo=None)
                changed = True
            converted.append({**entry, 'time': time.strftime('%Y-%m-%dT%H:%M')})
        if changed:
            forecast.hourly = converted
            forecast.save(update_fields=['hourly'])


class Migration(migrations.Migration):

    dependencies = [
        ('backoffice', '0089_delete_forecasts_without_hourly'),
    ]

    operations = [
        migrations.RunPython(hourly_times_to_utc, hourly_times_to_provider_local),
    ]
