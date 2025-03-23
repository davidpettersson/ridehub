# Generated by Django 5.1.6 on 2025-03-23 00:21

import django_fsm
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backoffice', '0015_route_updated_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='registration',
            name='cancelled_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='registration',
            name='confirmed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='registration',
            name='state',
            field=django_fsm.FSMField(default='submitted', max_length=50, protected=True),
        ),
    ]
