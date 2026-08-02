import logging

from celery import shared_task

from backoffice.checks.registration_checks import submitted_registration_has_been_processed
from backoffice.services.event_service import EventService
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
def refresh_forecasts() -> int:
    service = EventService()
    events = list(service.fetch_events_within_forecast_horizon())
    refreshed = service.refresh_forecasts(events)
    logger.info('Refreshed %s forecast windows for %s events', refreshed, len(events))
    return refreshed
