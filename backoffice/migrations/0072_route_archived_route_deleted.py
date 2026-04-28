from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backoffice', '0071_userprofile_emergency_contact_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='route',
            name='archived',
            field=models.BooleanField(default=False, help_text='Marked archived in Ride with GPS.'),
        ),
        migrations.AddField(
            model_name='route',
            name='deleted',
            field=models.BooleanField(default=False, help_text='No longer present in Ride with GPS feed.'),
        ),
    ]
