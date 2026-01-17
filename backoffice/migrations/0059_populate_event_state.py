from django.db import migrations


def populate_event_state(apps, schema_editor):
    Event = apps.get_model('backoffice', 'Event')

    Event.objects.filter(archived=True).update(state='archived')
    Event.objects.filter(archived=False, cancelled=True).update(state='cancelled')
    Event.objects.filter(archived=False, cancelled=False, visible=True).update(state='published')
    Event.objects.filter(archived=False, cancelled=False, visible=False).update(state='draft')


def reverse_populate_event_state(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('backoffice', '0058_event_state'),
    ]

    operations = [
        migrations.RunPython(
            populate_event_state,
            reverse_populate_event_state,
        ),
    ]
