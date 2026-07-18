import django.utils.timezone
from django.db import migrations, models


def delete_forecasts(apps, schema_editor):
    apps.get_model('backoffice', 'Forecast').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('backoffice', '0083_rename_aqi_forecast_aqhi'),
    ]

    operations = [
        migrations.RunPython(delete_forecasts, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name='forecast',
            name='unique_forecast_location_time',
        ),
        migrations.RemoveIndex(
            model_name='forecast',
            name='backoffice__latitud_95ef8c_idx',
        ),
        migrations.AddField(
            model_name='forecast',
            name='end_time',
            field=models.DateTimeField(
                default=django.utils.timezone.now,
                help_text='Last hour included in the forecast window, always at the top of the hour.',
            ),
            preserve_default=False,
        ),
        migrations.RenameField(
            model_name='forecast',
            old_name='aqhi',
            new_name='aqhi_min',
        ),
        migrations.AlterField(
            model_name='forecast',
            name='aqhi_min',
            field=models.PositiveIntegerField(
                help_text='Lowest Canadian Air Quality Health Index during the forecast window (1-10, 11 means above 10).'
            ),
        ),
        migrations.AddField(
            model_name='forecast',
            name='aqhi_max',
            field=models.PositiveIntegerField(
                default=1,
                help_text='Highest Canadian Air Quality Health Index during the forecast window (1-10, 11 means above 10).',
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='forecast',
            name='time',
            field=models.DateTimeField(
                help_text='Hour the forecast window starts at, always at the top of the hour.'
            ),
        ),
        migrations.AlterField(
            model_name='forecast',
            name='precipitation',
            field=models.CharField(
                max_length=32,
                help_text='Comma-separated precipitation categories occurring during the forecast window.',
            ),
        ),
        migrations.AlterField(
            model_name='forecast',
            name='temperature_min',
            field=models.IntegerField(
                help_text='Minimum temperature in Celsius during the forecast window.'
            ),
        ),
        migrations.AlterField(
            model_name='forecast',
            name='temperature_max',
            field=models.IntegerField(
                help_text='Maximum temperature in Celsius during the forecast window.'
            ),
        ),
        migrations.AddConstraint(
            model_name='forecast',
            constraint=models.UniqueConstraint(
                fields=('latitude', 'longitude', 'time', 'end_time'),
                name='unique_forecast_location_window',
            ),
        ),
        migrations.AddIndex(
            model_name='forecast',
            index=models.Index(
                fields=['latitude', 'longitude', 'time', 'end_time'],
                name='forecast_location_window_idx',
            ),
        ),
    ]
