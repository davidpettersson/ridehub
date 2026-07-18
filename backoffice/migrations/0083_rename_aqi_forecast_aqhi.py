from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backoffice', '0082_forecast'),
    ]

    operations = [
        migrations.RenameField(
            model_name='forecast',
            old_name='aqi',
            new_name='aqhi',
        ),
        migrations.AlterField(
            model_name='forecast',
            name='aqhi',
            field=models.PositiveIntegerField(
                help_text='Canadian Air Quality Health Index at the forecast hour (1-10, 11 means above 10).'
            ),
        ),
    ]
