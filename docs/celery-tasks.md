# Celery tasks

Background work runs on the `worker` dyno, which also carries the beat scheduler
(`-B`) using `django_celery_beat`'s `DatabaseScheduler`.

## Tasks

| Task | Trigger | What it does |
| --- | --- | --- |
| `backoffice.tasks.alert_unconfirmed_registrations` | Beat, hourly at :05 | Emails `REGISTRATION_ALERT_EMAILS` about registrations stuck in `submitted` or `unverified` for more than one hour |
| `backoffice.tasks.fetch_forecast` | Enqueued by the web dyno | Fetches weather and air quality from Open-Meteo off the request path |
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

Gated behind the `async_forecast_fetch` waffle flag. With the flag off, the
forecast endpoints fetch from Open-Meteo inline, exactly as before.

With the flag on, `/events/<id>/forecast-badge` and `/upcoming/forecast-badges`
serve whatever forecast is already cached and enqueue `fetch_forecast` for any
window that needs refreshing. The badge re-polls every two seconds, up to five
attempts, and then gives up for that page load. A stale cached forecast is shown
immediately rather than held back while the refresh runs.

Events with no possible forecast — virtual events, and events outside the
seven-day horizon — render an empty badge instead of polling for a forecast that
will never arrive.

Enqueueing is deduplicated through a cache lock: a window that has been requested
is locked for `FORECAST_REQUEST_LOCK_SECONDS` (60s), so repeated poll attempts
and concurrent visitors do not pile up duplicate tasks for the same window.

The lock uses its own cache alias (`forecast`), backed by Redis when `REDIS_URL`
is set so it holds across dynos. The `default` cache stays in-process on purpose:
waffle reads every flag through it, so putting it on Redis would make flag
evaluation — and therefore most page renders — depend on Redis being reachable.
A failing forecast cache is caught and logged; the page still renders.

Note that the two Redis URLs are not interchangeable. Celery goes through kombu,
which wants `ssl_cert_reqs=CERT_NONE`; the Django cache goes through redis-py,
which only accepts `none`, `optional`, or `required` and raises on anything else.
`ridehub/redis_url.py` exposes `celery_redis_url()` and `cache_redis_url()` for
this reason.

## Behaviour without a worker

Nothing in the request path depends on a worker being up.

With `async_forecast_fetch` off — the default — no task is enqueued at all, so
the site behaves exactly as it did before this was added.

With the flag on and no worker consuming the queue, badges poll five times, find
nothing, and disappear for that page load. Pages render normally and the next
page load tries again. Beat tasks simply do not run, so no alert emails are sent.

If the broker itself is unreachable, `request_forecasts` logs a warning, releases
its lock so a later request can retry, and the page still renders — serving a
stale cached forecast when one exists. Publishing is configured to fail fast
(`CELERY_TASK_PUBLISH_RETRY = False`, 2s socket timeouts) so a dead broker does
not stall web requests behind connection retries.

## Knowing whether the schedule is running

`CeleryIntegration(monitor_beat_tasks=True)` registers a Sentry Cron monitor per
`CELERY_BEAT_SCHEDULE` entry and checks in on every run, so Sentry alerts on a
run that never happened rather than only on one that raised. Monitors appear
under Crons in Sentry after the first run of each task; their schedules come from
`CELERY_BEAT_SCHEDULE` and need no setup in Sentry.

This matters because a successful run is otherwise silent. `check_registrations`
logs only when it finds a stuck registration, and `alert_unconfirmed_registrations`
emails only when something is past the threshold, so an idle worker and a dead
worker look identical from the outside.

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

To turn on async forecast fetching, add the `async_forecast_fetch` flag at
`/admin/waffle/flag/` and set it to Everyone → Yes.

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
