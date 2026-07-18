import logging
import math
from collections import Counter
from datetime import timedelta, timezone as datetime_timezone
from decimal import Decimal

import requests
from django.utils import timezone

from backoffice.models import Forecast

logger = logging.getLogger(__name__)

YOW_LOCATION = (Decimal('45.32250'), Decimal('-75.66920'))

FORECAST_MAX_AGE = timedelta(hours=1)
FORECAST_WINDOW = timedelta(days=7)
REQUEST_TIMEOUT_SECONDS = 3

WEATHER_URL = 'https://api.open-meteo.com/v1/forecast'
AIR_QUALITY_URL = 'https://air-quality-api.open-meteo.com/v1/air-quality'


class ForecastService:
    def get_forecast(self, latitude: Decimal, longitude: Decimal, starts_at, ends_at=None) -> Forecast | None:
        time = self._snap_to_hour(starts_at)
        end_time = self._snap_to_hour_ceiling(ends_at) if ends_at else time + timedelta(hours=1)
        now = timezone.now()

        horizon = self._snap_to_hour_ceiling(now + FORECAST_WINDOW)
        end_time = min(end_time, horizon)
        if end_time < time:
            end_time = time

        if time < self._snap_to_hour(now) or time > now + FORECAST_WINDOW:
            return None

        existing = Forecast.objects.filter(
            latitude=latitude, longitude=longitude, start_time=time, end_time=end_time
        ).first()
        if existing and existing.updated_at >= now - FORECAST_MAX_AGE:
            return existing

        try:
            metrics = self._fetch_metrics(latitude, longitude, time, end_time)
        except (requests.RequestException, KeyError, ValueError, IndexError, TypeError) as e:
            logger.warning(
                'Forecast fetch failed for (%s, %s) from %s to %s: %s',
                latitude, longitude, time, end_time, e,
            )
            return existing

        forecast, _ = Forecast.objects.update_or_create(
            latitude=latitude,
            longitude=longitude,
            start_time=time,
            end_time=end_time,
            defaults=metrics,
        )
        return forecast

    def get_forecasts_for_events(self, events) -> dict:
        latitude, longitude = YOW_LOCATION
        forecasts_by_window: dict = {}
        forecasts_by_event_id: dict = {}

        for event in events:
            if event.virtual:
                continue
            ends_at = event.starts_at + event.duration
            window = (self._snap_to_hour(event.starts_at), self._snap_to_hour_ceiling(ends_at))
            if window not in forecasts_by_window:
                forecasts_by_window[window] = self.get_forecast(
                    latitude, longitude, event.starts_at, ends_at
                )
            if forecasts_by_window[window]:
                forecasts_by_event_id[event.id] = forecasts_by_window[window]

        return forecasts_by_event_id

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
                'timezone': 'auto',
                'forecast_days': 8,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        weather.raise_for_status()
        weather_data = weather.json()

        weather_indexes = self._window_indexes(weather_data, time, end_time)
        weather_codes = self._series_values(weather_data, 'weather_code', weather_indexes)
        temperatures = self._series_values(weather_data, 'temperature_2m', weather_indexes)

        air_quality = requests.get(
            AIR_QUALITY_URL,
            params={
                'latitude': str(latitude),
                'longitude': str(longitude),
                'hourly': 'pm2_5,nitrogen_dioxide,ozone',
                'timezone': 'auto',
                'forecast_days': 7,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        air_quality.raise_for_status()
        air_quality_data = air_quality.json()

        aqhi_values = [
            self._compute_aqhi(air_quality_data['hourly'], index)
            for index in self._window_indexes(air_quality_data, time, end_time)
        ]

        return {
            'conditions': self._conditions_from_weather_codes(weather_codes),
            'temperature_min': round(min(temperatures)),
            'temperature_max': round(max(temperatures)),
            'aqhi_min': min(aqhi_values),
            'aqhi_max': max(aqhi_values),
        }

    @classmethod
    def _window_indexes(cls, data: dict, time, end_time) -> list[int]:
        indexes = []
        hour = time
        while hour <= end_time:
            hour_key, _ = cls._local_keys(hour, data['utc_offset_seconds'])
            try:
                indexes.append(data['hourly']['time'].index(hour_key))
            except ValueError:
                break
            hour += timedelta(hours=1)
        if not indexes:
            raise ValueError(f'No forecast data available between {time} and {end_time}')
        return indexes

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
    def _local_keys(time, utc_offset_seconds: int) -> tuple[str, str]:
        local = time.astimezone(datetime_timezone(timedelta(seconds=utc_offset_seconds)))
        return local.strftime('%Y-%m-%dT%H:%M'), local.strftime('%Y-%m-%d')

    @classmethod
    def _conditions_from_weather_codes(cls, codes: list) -> str:
        hour_counts = Counter(cls._condition_from_weather_code(int(code)) for code in codes)
        severity = list(reversed(Forecast.Condition))
        ordered = sorted(
            hour_counts,
            key=lambda category: (-hour_counts[category], severity.index(category)),
        )
        return ','.join(ordered)

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
