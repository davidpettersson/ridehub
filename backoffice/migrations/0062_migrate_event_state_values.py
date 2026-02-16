from django.db import migrations


def migrate_state_values_forward(apps, schema_editor):
    Event = apps.get_model('backoffice', 'Event')
    Event.objects.filter(state='preview').update(state='announced')
    Event.objects.filter(state='published').update(state='open')


def migrate_state_values_reverse(apps, schema_editor):
    Event = apps.get_model('backoffice', 'Event')
    Event.objects.filter(state='announced').update(state='preview')
    Event.objects.filter(state='open').update(state='published')


class Migration(migrations.Migration):

    dependencies = [
        ('backoffice', '0061_rename_event_states'),
    ]

    operations = [
        migrations.RunPython(
            migrate_state_values_forward,
            migrate_state_values_reverse,
        ),
    ]
