from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('membership', '0014_registration_member_remove_match'),
    ]

    operations = [
        migrations.RenameField(
            model_name='registration',
            old_name='member',
            new_name='matched_member',
        ),
    ]
