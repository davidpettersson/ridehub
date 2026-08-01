# Celery tasks

Background work runs on the `worker` dyno, which also carries the beat scheduler
(`-B`) using `django_celery_beat`'s `DatabaseScheduler`.

## Tasks

| Task | Trigger | What it does |
| --- | --- | --- |
| `backoffice.tasks.alert_unconfirmed_registrations` | Beat, hourly at :05 | Emails `REGISTRATION_ALERT_EMAILS` about registrations stuck in `submitted` or `unverified` for more than one hour |
| `backoffice.tasks.fetch_forecast` | Enqueued by the web dyno | Fetches weather and air quality from Open-Meteo off the request path |
| `backoffice.tasks.check_registrations` | Beat, every 15 minutes | Logs registrations stuck in `submitted` |
| `backoffice.tasks.debug_ping` | `POST /debug/trigger-task` | Logs a message; used to confirm the worker is consuming the queue |

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

```
curl -X POST https://<host>/debug/trigger-task -d 'message=hello' -b '<staff session cookie>'
heroku logs --tail --dyno worker
```

The endpoint is staff-only and returns the task id as JSON; the worker logs
`debug_ping received hello`.
