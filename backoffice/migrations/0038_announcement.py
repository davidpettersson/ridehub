# Generated by Django 5.1.6 on 2025-06-10 23:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backoffice', '0037_alter_event_ends_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='Announcement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('begin_at', models.DateTimeField(help_text='Time when the announcement should begin.')),
                ('end_at', models.DateTimeField(help_text='Time when the announcement should end.')),
                ('title', models.CharField(help_text='Name of the announcement. Will not be shown on the public pages.', max_length=128)),
                ('text', models.TextField(help_text='Announcement text. Keep formatting to a minimum.')),
            ],
        ),
    ]
