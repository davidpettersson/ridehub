from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('membership', '0015_rename_member_to_matched_member'),
    ]

    operations = [
        migrations.RenameField(
            model_name='member',
            old_name='user',
            new_name='matched_user',
        ),
    ]
