import logging
from decimal import Decimal

from celery import shared_task
from django.utils.dateparse import parse_datetime

from backoffice.checks.registration_checks import submitted_registration_has_been_processed
from backoffice.services.forecast_service import ForecastService
from backoffice.services.registration_alert_service import RegistrationAlertService

logger = logging.getLogger(__name__)


@shared_task
def debug_ping(message: str = 'ping') -> str:
    logger.info('debug_ping received %s', message)
    return message


@shared_task
def check_registrations():
    submitted_registration_has_been_processed()


@shared_task
def alert_unconfirmed_registrations() -> int:
    return RegistrationAlertService().alert_unconfirmed_registrations()


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={'max_retries': 3},
)
def fetch_forecast(latitude: str, longitude: str, starts_at: str, ends_at: str) -> int | None:
    forecast = ForecastService().get_forecast(
        Decimal(latitude),
        Decimal(longitude),
        parse_datetime(starts_at),
        parse_datetime(ends_at),
    )
    return forecast.id if forecast else None
