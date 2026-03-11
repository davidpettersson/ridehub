from django.db import migrations


def normalize_phone_numbers(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('backoffice', '0066_usermembershipnumber_updated_at'),
    ]

    operations = [
        migrations.RunPython(
            normalize_phone_numbers,
            migrations.RunPython.noop,
        ),
    ]
