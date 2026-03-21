from django.db import migrations, models


def convert_archived_to_cancelled(apps, schema_editor):
    Event = apps.get_model('backoffice', 'Event')
    Event.objects.filter(state='archived').update(state='cancelled')


class Migration(migrations.Migration):

    dependencies = [
        ('backoffice', '0068_normalize_phone_numbers_v2'),
    ]

    operations = [
        migrations.RunPython(
            convert_archived_to_cancelled,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name='event',
            name='archived_at',
        ),
        migrations.AlterField(
            model_name='event',
            name='state',
            field=models.CharField(
                choices=[
                    ('draft', 'Draft'),
                    ('announced', 'Announced'),
                    ('live', 'Live'),
                    ('cancelled', 'Cancelled'),
                ],
                default='live',
                help_text='Draft: not visible to public. Announced: visible but registration closed. Live: visible with registration open.',
                max_length=50,
            ),
        ),
    ]
