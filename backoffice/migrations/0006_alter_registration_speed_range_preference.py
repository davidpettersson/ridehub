# Generated by Django 5.1.6 on 2025-02-26 03:39

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backoffice', '0005_remove_ride_point_of_departure_event_location'),
    ]

    operations = [
        migrations.AlterField(
            model_name='registration',
            name='speed_range_preference',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='backoffice.speedrange'),
        ),
    ]
