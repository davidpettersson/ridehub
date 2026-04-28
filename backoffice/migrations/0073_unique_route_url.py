from django.db import migrations, models
from django.db.models import Count


def empty_url_to_null(apps, schema_editor):
    Route = apps.get_model('backoffice', 'Route')
    affected = Route.objects.filter(url='').update(url=None)
    print(f'[0073] empty_url_to_null: normalized {affected} blank URL(s) to NULL')


def null_url_to_empty(apps, schema_editor):
    Route = apps.get_model('backoffice', 'Route')
    affected = Route.objects.filter(url__isnull=True).update(url='')
    print(f'[0073] null_url_to_empty: restored {affected} NULL URL(s) to blank')


def merge_duplicate_urls(apps, schema_editor):
    Route = apps.get_model('backoffice', 'Route')
    Ride = apps.get_model('backoffice', 'Ride')
    dupe_urls = list(
        Route.objects.exclude(url__isnull=True)
        .values('url')
        .annotate(c=Count('id'))
        .filter(c__gt=1)
        .values_list('url', flat=True)
    )
    if not dupe_urls:
        print('[0073] merge_duplicate_urls: no duplicates found')
        return
    print(f'[0073] merge_duplicate_urls: {len(dupe_urls)} duplicate URL group(s) to merge')
    total_repointed = 0
    total_deleted = 0
    for url in dupe_urls:
        routes = list(Route.objects.filter(url=url).order_by('id'))
        canonical = routes[0]
        dupe_ids = [r.id for r in routes[1:]]
        repointed = Ride.objects.filter(route_id__in=dupe_ids).update(route_id=canonical.id)
        deleted, _ = Route.objects.filter(id__in=dupe_ids).delete()
        total_repointed += repointed
        total_deleted += deleted
        print(
            f'[0073]   {url}: keeping Route id={canonical.id}, '
            f'merging {len(dupe_ids)} dupe(s) {dupe_ids}, '
            f'repointed {repointed} Ride(s), deleted {deleted} Route row(s)'
        )
    print(
        f'[0073] merge_duplicate_urls: total {total_repointed} Ride(s) repointed, '
        f'{total_deleted} Route row(s) deleted'
    )


def flush_deferred_constraints(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute('SET CONSTRAINTS ALL IMMEDIATE')
        print('[0073] flush_deferred_constraints: fired pending FK triggers')


class Migration(migrations.Migration):

    dependencies = [
        ('backoffice', '0072_route_archived_route_deleted'),
    ]

    operations = [
        migrations.AlterField(
            model_name='route',
            name='url',
            field=models.URLField(
                blank=True,
                null=True,
                help_text='Ride with GPS URL. If this is set, then whenever an import from Ride with GPS happens other fields will be overwritten for this route.',
                verbose_name='Ride With GPS URL',
            ),
        ),
        migrations.RunPython(empty_url_to_null, null_url_to_empty),
        migrations.RunPython(merge_duplicate_urls, migrations.RunPython.noop),
        migrations.RunPython(flush_deferred_constraints, migrations.RunPython.noop),
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
