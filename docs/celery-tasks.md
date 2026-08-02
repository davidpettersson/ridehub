# Celery tasks

Background work runs on the `worker` dyno, which also carries the beat scheduler
(`-B`) using `django_celery_beat`'s `DatabaseScheduler`.

## Tasks

| Task | Trigger | What it does |
| --- | --- | --- |
| `backoffice.tasks.alert_unconfirmed_registrations` | Beat, hourly at :05 | Emails `REGISTRATION_ALERT_EMAILS` about registrations stuck in `submitted` or `unverified` for more than one hour |
| `backoffice.tasks.refresh_forecasts` | Beat, hourly at :42 | Fetches weather and air quality from Open-Meteo for every visible event starting in the next seven days |
| `backoffice.tasks.debug_ping` | `/debug/tasks-ping` | Logs a message; used to confirm the worker is consuming the queue |

## Unconfirmed registration alerts

The alert is a digest of everything currently over the threshold, and it repeats
every hour until each registration is confirmed or withdrawn. There is no
per-registration alert state, so a registration that stays unconfirmed appears in
every hourly email until it is dealt with.

Recipients come from `REGISTRATION_ALERT_EMAILS`, a comma-separated list. When it
is empty the task logs a warning and sends nothing.

## Forecast fetching

`refresh_forecasts` runs hourly, at :42 rather than on the hour so the
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

How often a window is actually refetched depends on how far out the event is:
one hour when it starts within a day, twelve hours when it is seven days out,
interpolated linearly and rounded to the closest hour in between (48h out → 3h,
96h out → 6h, 144h out → 10h). A forecast is stale once it is older than twice
that interval, measured from the event start or from now, whichever comes first.
See `docs/weather-forecast-algorithm.md` for the formula.

Each run checks freshness first and fetches only the windows whose latest row is
stale. Running the task several times in a row — a beat run landing near a manual
`/debug/tasks-refresh-forecasts` trigger, say — costs one set of requests, not
one per run. Rows are still append-only: a refetch adds a revision rather than
replacing one, and `/events/<id>/forecasts` shows every revision regardless of
age.

For an event that has already started, the stale rule anchors on its start, where
the interval is one hour: it keeps the last forecast prepared in the two hours
before it began, and that keeps showing indefinitely — an old event's badge is a
record of what was predicted, and it never goes stale.

A fetch or parse failure against Open-Meteo is caught per window, logged, and
leaves the previous row untouched; the run continues with the remaining windows
and does not retry, since the next run is at most an hour away. The task's
`autoretry_for` covers only errors that escape that handling — a database
failure, say — and retries those with backoff up to three times.

## Behaviour without a worker

Nothing in the request path depends on a worker being up. Pages render from
whatever forecast rows exist; with no worker those rows stop being refreshed and
badges disappear once they go stale — two hours later for an event starting
within a day, up to a day later for one a week out. Beat tasks simply do not run, so no alert
emails are sent either.

## Knowing whether the schedule is running

`CeleryIntegration(monitor_beat_tasks=True)` registers a Sentry Cron monitor per
`CELERY_BEAT_SCHEDULE` entry and checks in on every run, so Sentry alerts on a
run that never happened rather than only on one that raised. Monitors appear
under Crons in Sentry after the first run of each task; their schedules come from
`CELERY_BEAT_SCHEDULE` and need no setup in Sentry.

This matters because a successful run is otherwise silent.
`alert_unconfirmed_registrations` emails only when something is past the
threshold, and a missed `refresh_forecasts`
run shows up only as badges quietly vanishing, so an idle worker and a dead worker
look identical from the outside.

`refresh_forecasts` also logs its own progress at INFO: how many events it is
about to cover and how many are skipped as virtual, one line per stored row
(`Stored forecast <id> for <start> to <end> with <n> hourly readings`), how many
of the distinct windows were refreshed and how many were already fresh, and a
closing summary. A run that fetched
nothing says so explicitly rather than logging nothing at all, so an empty
horizon is distinguishable from a task that never ran. Failures stay at WARNING
with the window and the underlying error.

The other signals, in decreasing usefulness: `last_run_at` and `total_run_count`
at `/admin/django_celery_beat/periodictask/`; `Scheduler: Sending due task` lines
in the worker log; and `/debug/tasks-ping` to prove the queue is being consumed
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

Sign in as a superuser and open `/debug/tasks-ping`. The page has a message field and
a Queue task button; submitting it shows the queued task id, and the worker log
shows `debug_ping received <message>`.

```
heroku logs --tail --dyno worker
```

If the broker is unreachable the page shows the connection error instead of
returning a 500, which distinguishes "no worker running" from "cannot reach
Redis at all".
