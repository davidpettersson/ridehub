import logging
import math
from dataclasses import dataclass
from datetime import timedelta, timezone as datetime_timezone
from decimal import Decimal

import requests
from django.db.models import QuerySet
from django.utils import timezone

from backoffice.models import Forecast

logger = logging.getLogger(__name__)

YOW_LOCATION = (Decimal('45.32250'), Decimal('-75.66920'))

FORECAST_MAX_AGE = timedelta(hours=1)
FORECAST_WINDOW = timedelta(days=7)
REQUEST_TIMEOUT_SECONDS = 3

WEATHER_URL = 'https://api.open-meteo.com/v1/forecast'
AIR_QUALITY_URL = 'https://air-quality-api.open-meteo.com/v1/air-quality'


@dataclass(frozen=True)
class ForecastState:
    forecast: Forecast | None = None
    pending: bool = False

    @classmethod
    def ready(cls, forecast: Forecast) -> 'ForecastState':
        return cls(forecast=forecast)

    @classmethod
    def pending_fetch(cls) -> 'ForecastState':
        return cls(pending=True)

    @classmethod
    def unavailable(cls) -> 'ForecastState':
        return cls()

    @property
    def possible(self) -> bool:
        return self.forecast is not None or self.pending


class ForecastService:
    def get_forecast(self, latitude: Decimal, longitude: Decimal, starts_at, ends_at=None) -> Forecast | None:
        now = timezone.now()
        window = self._resolve_window(starts_at, ends_at, now)
        if window is None:
            return None
        time, end_time = window

        latest = self._latest_forecast(latitude, longitude, time, end_time)
        if latest and self._is_fresh(latest, now):
            return latest

        try:
            metrics = self._fetch_metrics(latitude, longitude, time, end_time)
        except (requests.RequestException, KeyError, ValueError, IndexError, TypeError) as e:
            logger.warning(
                'Forecast fetch failed for (%s, %s) from %s to %s: %s',
                latitude, longitude, time, end_time, e,
            )
            return latest

        return Forecast.objects.create(
            latitude=latitude,
            longitude=longitude,
            start_time=time,
            end_time=end_time,
            **metrics,
        )

    def resolve(self, latitude: Decimal, longitude: Decimal, starts_at, ends_at=None) -> ForecastState:
        now = timezone.now()
        window = self._resolve_window(starts_at, ends_at, now)
        if window is None:
            return ForecastState.unavailable()
        time, end_time = window

        latest = self._latest_forecast(latitude, longitude, time, end_time)
        if latest and self._is_fresh(latest, now):
            return ForecastState.ready(latest)
        return ForecastState.pending_fetch()

    def get_forecasts_for_windows(self, windows) -> dict:
        return self._lookup_by_window(windows, self.get_forecast)

    def resolve_for_windows(self, windows) -> dict:
        return self._lookup_by_window(windows, self.resolve)

    def _lookup_by_window(self, windows, lookup) -> dict:
        latitude, longitude = YOW_LOCATION
        forecasts_by_snapped_window: dict = {}
        forecasts_by_window: dict = {}

        for window in windows:
            starts_at, ends_at = window
            snapped_window = (self._snap_to_hour(starts_at), self._snap_to_hour_ceiling(ends_at))
            if snapped_window not in forecasts_by_snapped_window:
                forecasts_by_snapped_window[snapped_window] = lookup(
                    latitude, longitude, starts_at, ends_at
                )
            forecasts_by_window[window] = forecasts_by_snapped_window[snapped_window]

        return forecasts_by_window

    @classmethod
    def _resolve_window(cls, starts_at, ends_at, now) -> tuple | None:
        time = cls._snap_to_hour(starts_at)
        end_time = cls._snap_to_hour_ceiling(ends_at) if ends_at else time + timedelta(hours=1)

        horizon = cls._snap_to_hour_ceiling(now + FORECAST_WINDOW)
        end_time = min(end_time, horizon)
        if end_time < time:
            end_time = time

        if time < cls._start_of_current_day(now) or time > now + FORECAST_WINDOW:
            return None

        return time, end_time

    @staticmethod
    def _start_of_current_day(now):
        local_midnight = timezone.localtime(now).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return local_midnight.astimezone(datetime_timezone.utc)

    @staticmethod
    def _latest_forecast(latitude: Decimal, longitude: Decimal, time, end_time) -> Forecast | None:
        return Forecast.objects.filter(
            latitude=latitude, longitude=longitude, start_time=time, end_time=end_time
        ).order_by('-prepared_at').first()

    @staticmethod
    def _is_fresh(forecast: Forecast, now) -> bool:
        return forecast.prepared_at >= now - FORECAST_MAX_AGE

    def get_forecast_history(self, latitude: Decimal, longitude: Decimal, starts_at, ends_at=None) -> QuerySet:
        time = self._snap_to_hour(starts_at)
        end_time = self._snap_to_hour_ceiling(ends_at) if ends_at else time + timedelta(hours=1)

        return Forecast.objects.filter(
            latitude=latitude, longitude=longitude, start_time=time, end_time=end_time
        ).exclude(hourly=[]).order_by('-prepared_at')

    @staticmethod
    def _snap_to_hour(value):
        return value.replace(minute=0, second=0, microsecond=0)

    @classmethod
    def _snap_to_hour_ceiling(cls, value):
        snapped = cls._snap_to_hour(value)
        if snapped == value:
            return snapped
        return snapped + timedelta(hours=1)

    def _fetch_metrics(self, latitude: Decimal, longitude: Decimal, time, end_time) -> dict:
        weather = requests.get(
            WEATHER_URL,
            params={
                'latitude': str(latitude),
                'longitude': str(longitude),
                'hourly': 'weather_code,temperature_2m',
                'timezone': 'UTC',
                'forecast_days': 8,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        weather.raise_for_status()
        weather_data = weather.json()

        weather_hours = self._window_hours(weather_data, time, end_time)
        weather_indexes = [index for _, index in weather_hours]
        weather_codes = self._series_values(weather_data, 'weather_code', weather_indexes)
        temperatures = self._series_values(weather_data, 'temperature_2m', weather_indexes)

        air_quality = requests.get(
            AIR_QUALITY_URL,
            params={
                'latitude': str(latitude),
                'longitude': str(longitude),
                'hourly': 'pm2_5,nitrogen_dioxide,ozone',
                'timezone': 'UTC',
                'forecast_days': 7,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        air_quality.raise_for_status()
        air_quality_data = air_quality.json()

        aqhi_by_hour = self._aqhi_by_hour(air_quality_data, time, end_time)

        hourly = [
            {
                'time': hour.isoformat(),
                'condition': self._condition_from_weather_code(int(code)),
                'temperature': round(temperature),
                'aqhi': aqhi_by_hour.get(hour),
            }
            for (hour, _), code, temperature in zip(weather_hours, weather_codes, temperatures)
        ]

        return {'hourly': hourly}

    @classmethod
    def _aqhi_by_hour(cls, air_quality_data: dict, time, end_time) -> dict:
        aqhi_by_hour = {}
        for hour, index in cls._window_hours(air_quality_data, time, end_time, required=False):
            try:
                aqhi_by_hour[hour] = cls._compute_aqhi(air_quality_data['hourly'], index)
            except ValueError:
                continue
        return aqhi_by_hour

    @classmethod
    def _window_hours(cls, data: dict, time, end_time, required: bool = True) -> list[tuple]:
        hours = []
        hour = time
        while hour <= end_time:
            try:
                index = data['hourly']['time'].index(cls._hour_key(hour))
            except ValueError:
                break
            hours.append((hour.astimezone(datetime_timezone.utc), index))
            hour += timedelta(hours=1)
        if required and not hours:
            raise ValueError(f'No forecast data available between {time} and {end_time}')
        return hours

    @staticmethod
    def _series_values(data: dict, field: str, indexes: list[int]) -> list:
        values = [data['hourly'][field][index] for index in indexes]
        if any(v is None for v in values):
            raise ValueError(f'Missing {field} data in forecast window')
        return values

    NO2_UG_M3_PER_PPB = 1.88
    O3_UG_M3_PER_PPB = 1.96

    @classmethod
    def _compute_aqhi(cls, hourly: dict, hour_index: int) -> int:
        pm25, no2, o3 = cls._pollutant_averages(hourly, hour_index)

        no2_ppb = no2 / cls.NO2_UG_M3_PER_PPB
        o3_ppb = o3 / cls.O3_UG_M3_PER_PPB

        aqhi = (10 / 10.4) * 100 * (
            (math.exp(0.000871 * no2_ppb) - 1)
            + (math.exp(0.000537 * o3_ppb) - 1)
            + (math.exp(0.000487 * pm25) - 1)
        )
        return min(11, max(1, round(aqhi)))

    @staticmethod
    def _pollutant_averages(hourly: dict, hour_index: int) -> tuple[float, float, float]:
        series = (hourly['pm2_5'], hourly['nitrogen_dioxide'], hourly['ozone'])

        window = []
        for index in range(max(0, hour_index - 2), hour_index + 1):
            values = tuple(s[index] for s in series)
            if all(isinstance(v, (int, float)) for v in values):
                window.append(values)

        if not window:
            raise ValueError(f'No pollutant data available around hour index {hour_index}')

        return tuple(sum(values) / len(window) for values in zip(*window))

    @staticmethod
    def _hour_key(time) -> str:
        return time.astimezone(datetime_timezone.utc).strftime('%Y-%m-%dT%H:%M')

    @staticmethod
    def _condition_from_weather_code(code: int) -> str:
        if code >= 95:
            return Forecast.Condition.THUNDER
        if 71 <= code <= 77 or code in (85, 86):
            return Forecast.Condition.SNOW
        if code >= 51:
            return Forecast.Condition.RAIN
        if code >= 2:
            return Forecast.Condition.CLOUD
        return Forecast.Condition.SUN
