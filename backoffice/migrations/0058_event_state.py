import django_fsm
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backoffice', '0057_create_ride_administrators_group'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='state',
            field=django_fsm.FSMField(
                choices=[
                    ('draft', 'Draft'),
                    ('preview', 'Preview'),
                    ('published', 'Published'),
                    ('cancelled', 'Cancelled'),
                    ('archived', 'Archived'),
                ],
                default='published',
                help_text='Current state of the event in the lifecycle.',
                max_length=50,
                protected=False,
            ),
        ),
    ]
