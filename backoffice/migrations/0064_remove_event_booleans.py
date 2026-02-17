from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backoffice', '0063_rename_open_to_live'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='event',
            name='visible',
        ),
        migrations.RemoveField(
            model_name='event',
            name='cancelled',
        ),
        migrations.RemoveField(
            model_name='event',
            name='archived',
        ),
    ]
