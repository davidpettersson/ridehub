import logging

from celery import shared_task

from backoffice.services.event_service import EventService
from backoffice.services.registration_alert_service import RegistrationAlertService
from backoffice.services.registration_reminder_service import RegistrationReminderService

logger = logging.getLogger(__name__)


@shared_task
def debug_ping(message: str = 'ping') -> str:
    logger.info('debug_ping received %s', message)
    return message


@shared_task
def alert_unconfirmed_registrations() -> int:
    return RegistrationAlertService().alert_unconfirmed_registrations()


@shared_task
def remind_unconfirmed_registrations() -> int:
    return RegistrationReminderService().remind_unconfirmed_registrations()


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={'max_retries': 3},
)
def refresh_forecasts() -> int:
    service = EventService()
    events = list(service.fetch_events_within_forecast_horizon())

    if not events:
        logger.info('No events within the forecast horizon, nothing to refresh')
        return 0

    refreshed = service.refresh_forecasts(events)
    logger.info(
        'Forecast refresh finished: %s windows stored for %s events', refreshed, len(events)
    )
    return refreshed
