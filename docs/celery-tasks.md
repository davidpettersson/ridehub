# Celery tasks

Background work runs on the `worker` dyno, which also carries the beat scheduler
(`-B`) using `django_celery_beat`'s `DatabaseScheduler`.

## Tasks

| Task | Trigger | What it does |
| --- | --- | --- |
| `backoffice.tasks.alert_unconfirmed_registrations` | Beat, hourly at :05 | Emails `REGISTRATION_ALERT_EMAILS` about registrations stuck in `submitted` or `unverified` for more than one hour |
| `backoffice.tasks.refresh_forecasts` | Beat, every 2 hours at :23 | Fetches weather and air quality from Open-Meteo for every visible event starting in the next seven days |
| `backoffice.tasks.check_registrations` | Beat, every 15 minutes | Logs registrations stuck in `submitted` |
| `backoffice.tasks.debug_ping` | `/debug/trigger-task` | Logs a message; used to confirm the worker is consuming the queue |

## Unconfirmed registration alerts

The alert is a digest of everything currently over the threshold, and it repeats
every hour until each registration is confirmed or withdrawn. There is no
per-registration alert state, so a registration that stays unconfirmed appears in
every hourly email until it is dealt with.

Recipients come from `REGISTRATION_ALERT_EMAILS`, a comma-separated list. When it
is empty the task logs a warning and sends nothing.

## Forecast fetching

`refresh_forecasts` runs every two hours, at :23 rather than on the hour so the
requests do not land on the same top-of-hour spike as everyone else's cron. It
walks the visible, non-archived, non-virtual events starting between now and
seven days out, and writes a fresh `Forecast` row for each distinct hour window.
An event that has already started is never fetched again — its weather is
settled, and refetching would only overwrite what it was forecast to be with
what it turned out to be.
Events sharing a window — the usual case, since every ride starts from the same
coordinates — cost one fetch, not one per event.

The task is the only thing that calls Open-Meteo. Nothing in the request path
fetches: pages read stored `Forecast` rows and nothing else.

A forecast is displayable for six hours, measured from the event start or from
now, whichever comes first. For an upcoming event that means the usual freshness
rule: nothing older than six hours. For an event that has already started it means
the last forecast prepared in the six hours before it began, which keeps showing
indefinitely — an old event's badge is a record of what was predicted, and it
never goes stale. In steady state an upcoming event's data is at most two hours
old, so its badge only goes dark after roughly three consecutive failed runs.

Each run always writes new rows rather than skipping windows that already have
recent data; history is append-only, and `/events/<id>/forecasts` shows every
revision regardless of age.

A fetch that fails is logged and leaves the previous row untouched. The task
retries with backoff up to three times.

## Behaviour without a worker

Nothing in the request path depends on a worker being up. Pages render from
whatever forecast rows exist; with no worker those rows stop being refreshed and
badges disappear six hours later. Beat tasks simply do not run, so no alert
emails are sent either.

## Knowing whether the schedule is running

`CeleryIntegration(monitor_beat_tasks=True)` registers a Sentry Cron monitor per
`CELERY_BEAT_SCHEDULE` entry and checks in on every run, so Sentry alerts on a
run that never happened rather than only on one that raised. Monitors appear
under Crons in Sentry after the first run of each task; their schedules come from
`CELERY_BEAT_SCHEDULE` and need no setup in Sentry.

This matters because a successful run is otherwise silent. `check_registrations`
logs only when it finds a stuck registration, `alert_unconfirmed_registrations`
emails only when something is past the threshold, and a missed `refresh_forecasts`
run shows up only as badges quietly vanishing, so an idle worker and a dead worker
look identical from the outside.

The other signals, in decreasing usefulness: `last_run_at` and `total_run_count`
at `/admin/django_celery_beat/periodictask/`; `Scheduler: Sending due task` lines
in the worker log; and `/debug/trigger-task` to prove the queue is being consumed
right now.

## Heroku setup

```
heroku addons:create heroku-redis:mini
heroku config:set REGISTRATION_ALERT_EMAILS=you@example.com
heroku ps:scale worker=1
```

`REDIS_URL` is set by the add-on. `ridehub/celery.py` appends
`ssl_cert_reqs=CERT_NONE` to `rediss://` URLs, which Heroku's self-signed
certificates require, and raises on boot if `REDIS_URL` is missing on a dyno.

Worker concurrency is pinned to 2 in the `Procfile` and `CELERY_BROKER_POOL_LIMIT`
to 3. Without those, the prefork pool sizes itself from the host's core count and
exhausts the add-on's connection limit.

## Admin setup

`CELERY_BEAT_SCHEDULE` in `ridehub/settings.py` is the source of truth for the
periodic schedule. `DatabaseScheduler` syncs those entries into
`django_celery_beat` on worker startup, so no manual admin work is needed to get
them running.

Admin at `/admin/django_celery_beat/periodictask/` is for operational overrides:
disabling a task without a deploy, or adjusting a schedule temporarily. Edits
there are overwritten on the next worker restart for any task still present in
`CELERY_BEAT_SCHEDULE`.

## Verifying the worker

Sign in as staff and open `/debug/trigger-task`. The page has a message field and
a Queue task button; submitting it shows the queued task id, and the worker log
shows `debug_ping received <message>`.

```
heroku logs --tail --dyno worker
```

If the broker is unreachable the page shows the connection error instead of
returning a 500, which distinguishes "no worker running" from "cannot reach
Redis at all".
