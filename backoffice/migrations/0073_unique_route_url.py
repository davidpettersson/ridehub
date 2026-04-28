from django.db import migrations, models
from django.db.models import Count


def empty_url_to_null(apps, schema_editor):
    Route = apps.get_model('backoffice', 'Route')
    Route.objects.filter(url='').update(url=None)


def null_url_to_empty(apps, schema_editor):
    Route = apps.get_model('backoffice', 'Route')
    Route.objects.filter(url__isnull=True).update(url='')


def check_duplicate_urls(apps, schema_editor):
    Route = apps.get_model('backoffice', 'Route')
    duplicates = (
        Route.objects.exclude(url__isnull=True)
        .values('url')
        .annotate(c=Count('id'))
        .filter(c__gt=1)
    )
    duplicates = list(duplicates)
    if duplicates:
        details = ', '.join(f"{d['url']} ({d['c']})" for d in duplicates)
        raise RuntimeError(
            f"Cannot apply unique constraint on Route.url; duplicates found: {details}. "
            "Resolve duplicates manually before re-running migration."
        )


class Migration(migrations.Migration):

    dependencies = [
        ('backoffice', '0072_route_archived_route_deleted'),
    ]

    operations = [
        migrations.RunPython(empty_url_to_null, null_url_to_empty),
        migrations.RunPython(check_duplicate_urls, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='route',
            name='url',
            field=models.URLField(
                blank=True,
                null=True,
                unique=True,
                help_text='Ride with GPS URL. If this is set, then whenever an import from Ride with GPS happens other fields will be overwritten for this route.',
                verbose_name='Ride With GPS URL',
            ),
        ),
    ]
