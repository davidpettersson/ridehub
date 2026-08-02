# Weather Forecast Algorithm

This document describes how RideHub produces the weather badge shown on upcoming
events (`/upcoming` and `/event/<id>`). The implementation lives in
`backoffice/services/forecast_service.py` and the `Forecast` model.

## What is shown

All events except virtual ones that start today or within the next 7 days get a
badge:

```
☁️/⚡ · 12–15° · AQHI moderate →high
```

The badge summarizes the event's hours; `backoffice/services/forecast_summary.py`
reduces the stored hourly readings to the values below.

- **Condition**: one icon for the prevalent condition — the one covering the
  most hours of the window (thunder ⚡, snow ❄️, rain ☔, cloud ☁️, sun ☀️),
  ties broken toward the worse condition. A second icon follows when a notable
  condition (rain, snow, thunder) appears in some hour and is worse than the
  prevalent one.
- **Temperature**: minimum and maximum in °C across the event's duration,
  collapsed to a single midpoint when they span two degrees or less.
- **AQHI**: the prevalent Canadian Air Quality Health Index *category* (low,
  moderate, high, very high) rather than a number, plus a spike category when
  some hour lands in a worse category than the prevalent one. The badge omits
  AQHI entirely when the prevalent category is low and no hour rises above it,
  since a low reading is not actionable; a moderate or worse prevalent
  category, or a spike out of low, is always shown.

The hourly forecast modal is unaffected by that suppression: it lists each
hour's numeric AQHI (shown as `10+` above 10) and its category, whatever the
category is.

The badge credits its source: Open-Meteo.

## Data source

All data comes from [Open-Meteo](https://open-meteo.com/) (no API key):

- **Forecast API** (`api.open-meteo.com/v1/forecast`): hourly `weather_code`
  and `temperature_2m`, 8 forecast days.
- **Air Quality API** (`air-quality-api.open-meteo.com/v1/air-quality`): hourly
  `pm2_5`, `nitrogen_dioxide`, `ozone`, 7 forecast days (that API's maximum).

Both requests use `timezone=UTC`, so response hours are matched, stored and
compared as absolute times; the hourly readings are rendered in the site's
configured timezone at display time only. All events currently use a single
fixed location, YOW (Ottawa airport, 45.32250, -75.66920).

## Forecast window

1. The event start is snapped **down** to the top of the hour; the event end
   (`starts_at + duration`, where duration defaults to 1 hour when `ends_at`
   is blank) is snapped **up** to the next top of the hour.
2. Fetching covers only events that have not started yet and start within 7
   days. Display has no such bounds: any event with a usable stored row gets a
   badge, however far in the past, and the window always covers the whole event
   including hours that have already passed.
3. The window end is clamped to the 7-day horizon so cache keys stay bounded
   and deterministic. The stored `end_time` always describes the requested
   window, not the provider's data coverage.
4. The window is the inclusive list of hours from start to end. If the window
   extends beyond the hours the provider actually returned, the metrics cover
   the available hours; if no hours are available the fetch fails safely.

## Metrics

For each hour in the window:

- **Condition category** from the WMO weather code: 95+ thunder,
  71-77 and 85-86 snow, other codes 51-94 rain, 2-50 cloud, otherwise sun.
  The badge shows the distinct set of categories over the window, ordered by
  the number of hours each category covers (most prevalent first), with ties
  broken worst first.
- **Temperature** is `temperature_2m`; the badge shows the rounded min and max
  over the window.
- **AQHI** is computed with Environment Canada's formula from the 3-hour
  rolling average (the hour itself and up to two preceding hours) of PM2.5
  (µg/m³), NO₂ and O₃ (converted from µg/m³ to ppb by dividing by 1.88 and
  1.96 respectively):

  ```
  AQHI = (10 / 10.4) × 100 × [ (e^(0.000871 × NO₂) − 1)
                             + (e^(0.000537 × O₃) − 1)
                             + (e^(0.000487 × PM2.5) − 1) ]
  ```

  The result is rounded and clamped to 1..11, where 11 represents "above 10".
  Hours with incomplete pollutant data are dropped from the rolling average;
  if no data exists for an hour at all, the fetch fails safely. The badge
  shows the min and max AQHI over the window.

## Caching and refresh

- `Forecast` rows are immutable. Each fetch stores a new row stamped with
  `prepared_at`; older rows for the same window are preserved, so the history
  of how the forecast for a given time period evolved can be reconstructed.
- Lookups key on `(latitude, longitude, start_time, end_time)` and use the row
  with the latest `prepared_at`; events sharing the same snapped window share
  rows and fetches.
- Rows are written only by the `refresh_forecasts` beat task, which runs every
  two hours over the events starting in the next seven days and always fetches,
  with a 3-second timeout per request. Nothing is fetched on page load, and an
  event that has already started is never fetched again.
- A row is displayable for 6 hours, measured from the event start or from now,
  whichever is earlier. An upcoming event therefore needs a row prepared within
  the last 6 hours, and once the latest row is older than that no badge is
  rendered — no forecast is better than a wrong one. A past event keeps the last
  row prepared in the 6 hours before it started, indefinitely. The forecast
  history page is subject to neither rule and shows every stored row.
- On any fetch or parse error the previous row is left alone and no new row is
  written. A failure never breaks the page and a partial or
  invalid value is never stored: model validation enforces top-of-hour times,
  UTC-offset-carrying hourly timestamps,
  ordered min/max pairs, AQHI in 1..11, and known precipitation categories.
