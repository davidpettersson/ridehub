from django.db import migrations


def create_ride_administrators_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    group, created = Group.objects.get_or_create(name='Ride Administrators')
    if created:
        print("Data migration: Created 'Ride Administrators' group")


def reverse_create_ride_administrators_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name='Ride Administrators').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('backoffice', '0056_delete_member'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(
            create_ride_administrators_group,
            reverse_create_ride_administrators_group
        ),
    ]
