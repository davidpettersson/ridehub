import django.db.models.deletion
from django.db import migrations, models


def migrate_match_to_registration(apps, schema_editor):
    Match = apps.get_model('membership', 'Match')
    Registration = apps.get_model('membership', 'Registration')

    for match in Match.objects.all():
        Registration.objects.filter(id=match.registration_id).update(
            member_id=match.member_id
        )


def reverse_migration(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('membership', '0013_add_member_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='registration',
            name='member',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='membership.member',
            ),
        ),
        migrations.RunPython(migrate_match_to_registration, reverse_migration),
        migrations.DeleteModel(
            name='Match',
        ),
    ]
