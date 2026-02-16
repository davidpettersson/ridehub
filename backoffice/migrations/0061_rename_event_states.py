import django_fsm
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backoffice', '0060_alter_registration_state'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='state',
            field=django_fsm.FSMField(
                choices=[
                    ('draft', 'Draft'),
                    ('announced', 'Announced'),
                    ('open', 'Open'),
                    ('cancelled', 'Cancelled'),
                    ('archived', 'Archived'),
                ],
                default='open',
                help_text='Current state of the event in the lifecycle.',
                max_length=50,
                protected=False,
            ),
        ),
    ]
