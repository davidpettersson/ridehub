# Generated by Django 5.1.6 on 2025-05-12 03:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backoffice', '0033_alter_route_last_imported_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='route',
            name='url',
            field=models.URLField(blank=True, help_text='Ride with GPS URL. If this is set, then whenever an import from Ride with GPS happens other fields will be overwritten for this route.', verbose_name='Ride With GPS URL'),
        ),
    ]
