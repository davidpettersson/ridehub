# Generated by Django 5.1.6 on 2025-05-12 03:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backoffice', '0030_event_registration_limit'),
    ]

    operations = [
        migrations.AddField(
            model_name='route',
            name='distance',
            field=models.PositiveIntegerField(blank=True, help_text='Distance in kilometers.', null=True),
        ),
        migrations.AddField(
            model_name='route',
            name='elevation_gain',
            field=models.PositiveIntegerField(blank=True, help_text='Elevation gain in meters.', null=True),
        ),
        migrations.AlterField(
            model_name='route',
            name='name',
            field=models.CharField(help_text='Ride name.', max_length=128),
        ),
        migrations.AlterField(
            model_name='route',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, help_text='When this route was last updated.'),
        ),
        migrations.AlterField(
            model_name='route',
            name='url',
            field=models.URLField(blank=True, help_text='Ride with GPS URL.', verbose_name='Ride With GPS URL'),
        ),
    ]
