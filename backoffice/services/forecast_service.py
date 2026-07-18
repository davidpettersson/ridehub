import logging
from datetime import timedelta, timezone as datetime_timezone
from decimal import Decimal

import requests
from django.utils import timezone

from backoffice.models import Forecast

logger = logging.getLogger(__name__)

YOW_LOCATION = (Decimal('45.32250'), Decimal('-75.66920'))

FORECAST_MAX_AGE = timedelta(hours=1)
FORECAST_WINDOW = timedelta(days=3)
REQUEST_TIMEOUT_SECONDS = 3

WEATHER_URL = 'https://api.open-meteo.com/v1/forecast'
AIR_QUALITY_URL = 'https://air-quality-api.open-meteo.com/v1/air-quality'


class ForecastService:
    def get_forecast(self, latitude: Decimal, longitude: Decimal, starts_at) -> Forecast | None:
        time = self._snap_to_hour(starts_at)
        now = timezone.now()

        if time < self._snap_to_hour(now) or time > now + FORECAST_WINDOW:
            return None

        existing = Forecast.objects.filter(
            latitude=latitude, longitude=longitude, time=time
        ).first()
        if existing and existing.updated_at >= now - FORECAST_MAX_AGE:
            return existing

        try:
            metrics = self._fetch_metrics(latitude, longitude, time)
        except (requests.RequestException, KeyError, ValueError, IndexError, TypeError) as e:
            logger.warning('Forecast fetch failed for (%s, %s) at %s: %s', latitude, longitude, time, e)
            return existing

        forecast, _ = Forecast.objects.update_or_create(
            latitude=latitude,
            longitude=longitude,
            time=time,
            defaults=metrics,
        )
        return forecast

    def get_forecasts_for_events(self, events) -> dict:
        latitude, longitude = YOW_LOCATION
        forecasts_by_time: dict = {}
        forecasts_by_event_id: dict = {}

        for event in events:
            if event.cancelled or not event.has_rides:
                continue
            time = self._snap_to_hour(event.starts_at)
            if time not in forecasts_by_time:
                forecasts_by_time[time] = self.get_forecast(latitude, longitude, event.starts_at)
            if forecasts_by_time[time]:
                forecasts_by_event_id[event.id] = forecasts_by_time[time]

        return forecasts_by_event_id

    @staticmethod
    def _snap_to_hour(value):
        return value.replace(minute=0, second=0, microsecond=0)

    def _fetch_metrics(self, latitude: Decimal, longitude: Decimal, time) -> dict:
        weather = requests.get(
            WEATHER_URL,
            params={
                'latitude': str(latitude),
                'longitude': str(longitude),
                'hourly': 'weather_code',
                'daily': 'temperature_2m_min,temperature_2m_max',
                'timezone': 'auto',
                'forecast_days': 4,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        weather.raise_for_status()
        weather_data = weather.json()

        hour_key, date_key = self._local_keys(time, weather_data['utc_offset_seconds'])
        hour_index = weather_data['hourly']['time'].index(hour_key)
        weather_code = weather_data['hourly']['weather_code'][hour_index]
        day_index = weather_data['daily']['time'].index(date_key)

        air_quality = requests.get(
            AIR_QUALITY_URL,
            params={
                'latitude': str(latitude),
                'longitude': str(longitude),
                'hourly': 'us_aqi',
                'timezone': 'auto',
                'forecast_days': 4,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        air_quality.raise_for_status()
        air_quality_data = air_quality.json()

        aqi_hour_key, _ = self._local_keys(time, air_quality_data['utc_offset_seconds'])
        aqi_index = air_quality_data['hourly']['time'].index(aqi_hour_key)
        aqi = air_quality_data['hourly']['us_aqi'][aqi_index]

        return {
            'precipitation': self._precipitation_from_weather_code(int(weather_code)),
            'temperature_min': round(weather_data['daily']['temperature_2m_min'][day_index]),
            'temperature_max': round(weather_data['daily']['temperature_2m_max'][day_index]),
            'aqi': int(aqi),
        }

    @staticmethod
    def _local_keys(time, utc_offset_seconds: int) -> tuple[str, str]:
        local = time.astimezone(datetime_timezone(timedelta(seconds=utc_offset_seconds)))
        return local.strftime('%Y-%m-%dT%H:%M'), local.strftime('%Y-%m-%d')

    @staticmethod
    def _precipitation_from_weather_code(code: int) -> str:
        if code >= 95:
            return Forecast.Precipitation.THUNDER
        if code >= 51:
            return Forecast.Precipitation.RAIN
        if code >= 2:
            return Forecast.Precipitation.CLOUD
        return Forecast.Precipitation.SUN
