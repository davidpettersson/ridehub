import logging
import math
from datetime import datetime, timedelta, timezone as datetime_timezone
from decimal import Decimal
from functools import reduce
from itertools import count, takewhile
from operator import or_
from typing import NamedTuple

import requests
from django.db.models import Q, QuerySet
from django.utils import timezone

from backoffice.models import Forecast

logger = logging.getLogger(__name__)

YOW_LOCATION = (Decimal('45.32250'), Decimal('-75.66920'))

FORECAST_WINDOW = timedelta(days=7)
REQUEST_TIMEOUT_SECONDS = 3
REQUESTS_PER_WINDOW = 2

REFRESH_INTERVAL_MIN_HOURS = 1
REFRESH_INTERVAL_MAX_HOURS = 12
REFRESH_LEAD_MIN_HOURS = 24
REFRESH_LEAD_MAX_HOURS = 168
STALE_AFTER_INTERVALS = 2

# A run fetches its windows one after another, and prepared_at is stamped once a
# window's requests come back, so a stored forecast is always younger than the
# run's clock by however long the run took to reach it. due_from allows for that
# lag; without it a window is perpetually a fraction short of its interval and
# waits for the run after next.
#
# Worst case is every window timing out on both requests:
#   REQUEST_TIMEOUT_SECONDS * REQUESTS_PER_WINDOW * EXPECTED_REFRESH_RUN_WINDOWS
# doubled, to leave room for more events than we see today. Raise the window
# count if the season grows well past it. Any value here well under
# REFRESH_INTERVAL_MIN_HOURS keeps a second run from refetching what the first
# one just stored.
EXPECTED_REFRESH_RUN_WINDOWS = 10
MAX_REFRESH_RUN_DURATION = 2 * timedelta(
    seconds=REQUEST_TIMEOUT_SECONDS * REQUESTS_PER_WINDOW * EXPECTED_REFRESH_RUN_WINDOWS
)

NO2_UG_M3_PER_PPB = 1.88
O3_UG_M3_PER_PPB = 1.96

WEATHER_URL = 'https://api.open-meteo.com/v1/forecast'
AIR_QUALITY_URL = 'https://air-quality-api.open-meteo.com/v1/air-quality'


class Window(NamedTuple):
    start: datetime
    end: datetime


def snap_to_hour(value: datetime) -> datetime:
    return value.replace(minute=0, second=0, microsecond=0)


def snap_to_hour_ceiling(value: datetime) -> datetime:
    snapped = snap_to_hour(value)
    return snapped if snapped == value else snapped + timedelta(hours=1)


def raw_window(starts_at: datetime, ends_at: datetime | None) -> Window:
    start = snap_to_hour(starts_at)
    end = snap_to_hour_ceiling(ends_at) if ends_at else start + timedelta(hours=1)
    return Window(start, end)


def clamp_to_horizon(window: Window, now: datetime) -> Window:
    horizon = snap_to_hour_ceiling(now + FORECAST_WINDOW)
    return Window(window.start, max(window.start, min(window.end, horizon)))


def window_for(starts_at: datetime, ends_at: datetime | None, now: datetime) -> Window:
    return clamp_to_horizon(raw_window(starts_at, ends_at), now)


def hours_in(window: Window) -> list[datetime]:
    return list(takewhile(
        lambda hour: hour <= window.end,
        (window.start + timedelta(hours=n) for n in count()),
    ))


def within_forecast_range(starts_at: datetime, now: datetime) -> bool:
    return now < starts_at <= now + FORECAST_WINDOW


def refresh_interval(window_start: datetime, now: datetime) -> timedelta:
    lead_hours = (window_start - now).total_seconds() / 3600
    slope = (
        (REFRESH_INTERVAL_MAX_HOURS - REFRESH_INTERVAL_MIN_HOURS)
        / (REFRESH_LEAD_MAX_HOURS - REFRESH_LEAD_MIN_HOURS)
    )
    hours = REFRESH_INTERVAL_MIN_HOURS + (lead_hours - REFRESH_LEAD_MIN_HOURS) * slope
    return timedelta(hours=min(
        REFRESH_INTERVAL_MAX_HOURS, max(REFRESH_INTERVAL_MIN_HOURS, round(hours))
    ))


def usable_from(window_start: datetime, now: datetime) -> datetime:
    return min(now, window_start) - STALE_AFTER_INTERVALS * refresh_interval(window_start, now)


def usable(forecast: Forecast | None, window: Window, now: datetime) -> Forecast | None:
    if forecast is None or forecast.prepared_at < usable_from(window.start, now):
        return None
    return forecast


def due_from(window_start: datetime, now: datetime) -> datetime:
    return min(now, window_start) - refresh_interval(window_start, now) + MAX_REFRESH_RUN_DURATION


def due(forecast: Forecast | None, window: Window, now: datetime) -> bool:
    return forecast is None or forecast.prepared_at < due_from(window.start, now)


def hour_key(time: datetime) -> str:
    return time.astimezone(datetime_timezone.utc).strftime('%Y-%m-%dT%H:%M')


def indexed_hours(data: dict, window: Window) -> list[tuple[datetime, int]]:
    index_by_key = {key: index for index, key in enumerate(data['hourly']['time'])}
    available = takewhile(lambda hour: hour_key(hour) in index_by_key, hours_in(window))
    return [
        (hour.astimezone(datetime_timezone.utc), index_by_key[hour_key(hour)])
        for hour in available
    ]


def series_values(data: dict, field: str, indexes: list[int]) -> list:
    values = [data['hourly'][field][index] for index in indexes]
    if any(value is None for value in values):
        raise ValueError(f'Missing {field} data in forecast window')
    return values


def condition_from_weather_code(code: int) -> str:
    if code >= 95:
        return Forecast.Condition.THUNDER
    if 71 <= code <= 77 or code in (85, 86):
        return Forecast.Condition.SNOW
    if code >= 51:
        return Forecast.Condition.RAIN
    if code >= 2:
        return Forecast.Condition.CLOUD
    return Forecast.Condition.SUN


def pollutant_averages(hourly: dict, hour_index: int) -> tuple[float, float, float] | None:
    series = (hourly['pm2_5'], hourly['nitrogen_dioxide'], hourly['ozone'])
    rows = (
        tuple(values[index] for values in series)
        for index in range(max(0, hour_index - 2), hour_index + 1)
    )
    complete = [
        row for row in rows
        if all(isinstance(value, (int, float)) for value in row)
    ]
    if not complete:
        return None
    return tuple(sum(values) / len(complete) for values in zip(*complete))


def compute_aqhi(hourly: dict, hour_index: int) -> int | None:
    averages = pollutant_averages(hourly, hour_index)
    if averages is None:
        return None

    pm25, no2, o3 = averages
    aqhi = (10 / 10.4) * 100 * (
        (math.exp(0.000871 * (no2 / NO2_UG_M3_PER_PPB)) - 1)
        + (math.exp(0.000537 * (o3 / O3_UG_M3_PER_PPB)) - 1)
        + (math.exp(0.000487 * pm25) - 1)
    )
    return min(11, max(1, round(aqhi)))


def aqhi_by_hour(air_quality_data: dict, window: Window) -> dict:
    readings = (
        (hour, compute_aqhi(air_quality_data['hourly'], index))
        for hour, index in indexed_hours(air_quality_data, window)
    )
    return {hour: aqhi for hour, aqhi in readings if aqhi is not None}


def weather_by_hour(weather_data: dict, window: Window) -> dict:
    hours = indexed_hours(weather_data, window)
    if not hours:
        raise ValueError(f'No forecast data available between {window.start} and {window.end}')

    indexes = [index for _, index in hours]
    return {
        hour: (condition_from_weather_code(int(code)), round(temperature))
        for (hour, _), code, temperature in zip(
            hours,
            series_values(weather_data, 'weather_code', indexes),
            series_values(weather_data, 'temperature_2m', indexes),
        )
    }


def hourly_readings(weather: dict, aqhi: dict) -> list[dict]:
    return [
        {
            'time': hour.isoformat(),
            'condition': condition,
            'temperature': temperature,
            'aqhi': aqhi.get(hour),
        }
        for hour, (condition, temperature) in weather.items()
    ]


def _get_json(url: str, params: dict) -> dict:
    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


class ForecastService:
    def refresh_forecast(self, latitude: Decimal, longitude: Decimal, starts_at, ends_at=None,
                         now=None) -> Forecast | None:
        now = now or timezone.now()
        if not within_forecast_range(starts_at, now):
            return None
        return self._fetch_and_store(latitude, longitude, window_for(starts_at, ends_at, now))

    def refresh_forecasts_for_windows(self, windows, now=None) -> dict:
        now = now or timezone.now()
        latitude, longitude = YOW_LOCATION

        requested = [(window, window_for(window[0], window[1], now)) for window in windows]
        if not requested:
            return {}

        latest = self._latest_by_window({snapped for _, snapped in requested}, now)

        overdue = dict.fromkeys(
            snapped for window, snapped in requested
            if due(latest.get(snapped), snapped, now) and within_forecast_range(window[0], now)
        )
        fetched = {
            snapped: self._fetch_and_store(latitude, longitude, snapped)
            for snapped in overdue
        }

        logger.info(
            'Refreshed %s of %s distinct forecast windows, %s not yet due',
            len([forecast for forecast in fetched.values() if forecast]),
            len({snapped for _, snapped in requested}),
            len({snapped for _, snapped in requested} - set(overdue)),
        )

        return {
            window: fetched.get(snapped) or usable(latest.get(snapped), snapped, now)
            for window, snapped in requested
        }

    def get_forecast(self, starts_at, ends_at=None) -> Forecast | None:
        window = (starts_at, ends_at or starts_at + timedelta(hours=1))
        return self.get_forecasts_for_windows([window])[window]

    def get_forecasts_for_windows(self, windows, now=None) -> dict:
        now = now or timezone.now()

        snapped_by_window = {
            window: window_for(window[0], window[1], now) for window in windows
        }
        if not snapped_by_window:
            return {}

        latest = self._latest_by_window(set(snapped_by_window.values()), now)

        return {
            window: usable(latest.get(snapped), snapped, now)
            for window, snapped in snapped_by_window.items()
        }

    @staticmethod
    def _latest_by_window(windows: set, now: datetime) -> dict:
        latitude, longitude = YOW_LOCATION
        matches_a_window = reduce(
            or_, (Q(start_time=window.start, end_time=window.end) for window in windows)
        )

        candidates = Forecast.objects.with_readings().filter(
            matches_a_window,
            latitude=latitude,
            longitude=longitude,
            prepared_at__gte=min(usable_from(window.start, now) for window in windows),
        ).order_by('prepared_at')

        return {
            Window(forecast.start_time, forecast.end_time): forecast
            for forecast in candidates
        }

    def get_forecast_history(self, latitude: Decimal, longitude: Decimal, starts_at,
                             ends_at=None) -> QuerySet:
        window = raw_window(starts_at, ends_at)

        return Forecast.objects.with_readings().filter(
            latitude=latitude, longitude=longitude,
            start_time=window.start, end_time=window.end,
        ).order_by('-prepared_at')

    def _fetch_and_store(self, latitude: Decimal, longitude: Decimal,
                         window: Window) -> Forecast | None:
        try:
            readings = hourly_readings(
                weather_by_hour(self._weather_data(latitude, longitude), window),
                aqhi_by_hour(self._air_quality_data(latitude, longitude), window),
            )
        except (requests.RequestException, KeyError, ValueError, IndexError, TypeError) as e:
            logger.warning(
                'Forecast fetch failed for (%s, %s) from %s to %s: %s',
                latitude, longitude, window.start, window.end, e,
            )
            return None

        forecast = Forecast.objects.create(
            latitude=latitude,
            longitude=longitude,
            start_time=window.start,
            end_time=window.end,
            hourly=readings,
        )
        logger.info(
            'Stored forecast %s for %s to %s with %s hourly readings',
            forecast.id, window.start, window.end, len(forecast.hourly),
        )
        return forecast

    @staticmethod
    def _weather_data(latitude: Decimal, longitude: Decimal) -> dict:
        return _get_json(WEATHER_URL, {
            'latitude': str(latitude),
            'longitude': str(longitude),
            'hourly': 'weather_code,temperature_2m',
            'timezone': 'UTC',
            'forecast_days': 8,
        })

    @staticmethod
    def _air_quality_data(latitude: Decimal, longitude: Decimal) -> dict:
        return _get_json(AIR_QUALITY_URL, {
            'latitude': str(latitude),
            'longitude': str(longitude),
            'hourly': 'pm2_5,nitrogen_dioxide,ozone',
            'timezone': 'UTC',
            'forecast_days': 7,
        })
