import django_fsm
from django.db import migrations


def migrate_open_to_live(apps, schema_editor):
    Event = apps.get_model('backoffice', 'Event')
    Event.objects.filter(state='open').update(state='live')


def migrate_live_to_open(apps, schema_editor):
    Event = apps.get_model('backoffice', 'Event')
    Event.objects.filter(state='live').update(state='open')


class Migration(migrations.Migration):

    dependencies = [
        ('backoffice', '0062_migrate_event_state_values'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='state',
            field=django_fsm.FSMField(
                choices=[
                    ('draft', 'Draft'),
                    ('announced', 'Announced'),
                    ('live', 'Live'),
                    ('cancelled', 'Cancelled'),
                    ('archived', 'Archived'),
                ],
                default='live',
                help_text='Current state of the event in the lifecycle.',
                max_length=50,
                protected=False,
            ),
        ),
        migrations.RunPython(
            migrate_open_to_live,
            migrate_live_to_open,
        ),
    ]
