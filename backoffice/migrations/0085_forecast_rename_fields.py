from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backoffice', '0084_forecast_duration_window'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='forecast',
            name='unique_forecast_location_window',
        ),
        migrations.RemoveIndex(
            model_name='forecast',
            name='forecast_location_window_idx',
        ),
        migrations.RenameField(
            model_name='forecast',
            old_name='time',
            new_name='start_time',
        ),
        migrations.RenameField(
            model_name='forecast',
            old_name='precipitation',
            new_name='conditions',
        ),
        migrations.AlterField(
            model_name='forecast',
            name='conditions',
            field=models.CharField(
                max_length=32,
                help_text='Comma-separated weather conditions occurring during the forecast window, worst first.',
            ),
        ),
        migrations.AlterField(
            model_name='forecast',
            name='aqhi_min',
            field=models.PositiveIntegerField(
                verbose_name='AQHI min',
                help_text='Lowest Canadian Air Quality Health Index during the forecast window (1-10, 11 means above 10).',
            ),
        ),
        migrations.AlterField(
            model_name='forecast',
            name='aqhi_max',
            field=models.PositiveIntegerField(
                verbose_name='AQHI max',
                help_text='Highest Canadian Air Quality Health Index during the forecast window (1-10, 11 means above 10).',
            ),
        ),
        migrations.AddConstraint(
            model_name='forecast',
            constraint=models.UniqueConstraint(
                fields=('latitude', 'longitude', 'start_time', 'end_time'),
                name='unique_forecast_location_window',
            ),
        ),
        migrations.AddIndex(
            model_name='forecast',
            index=models.Index(
                fields=['latitude', 'longitude', 'start_time', 'end_time'],
                name='forecast_location_window_idx',
            ),
        ),
    ]
