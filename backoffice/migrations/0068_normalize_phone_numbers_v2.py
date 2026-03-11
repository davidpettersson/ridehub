import phonenumbers
from django.db import migrations


def normalize_phone_numbers(apps, schema_editor):
    UserProfile = apps.get_model('backoffice', 'UserProfile')
    Registration = apps.get_model('backoffice', 'Registration')

    for model in [UserProfile, Registration]:
        for obj in model.objects.exclude(phone='').exclude(phone__startswith='+'):
            try:
                parsed = phonenumbers.parse(str(obj.phone), 'CA')
                if phonenumbers.is_valid_number(parsed):
                    obj.phone = phonenumbers.format_number(
                        parsed, phonenumbers.PhoneNumberFormat.E164
                    )
                    obj.save(update_fields=['phone'])
            except phonenumbers.NumberParseException:
                pass


class Migration(migrations.Migration):

    dependencies = [
        ('backoffice', '0067_normalize_phone_numbers'),
    ]

    operations = [
        migrations.RunPython(
            normalize_phone_numbers,
            migrations.RunPython.noop,
        ),
    ]
