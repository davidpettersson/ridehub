import logging

from celery import shared_task

from backoffice.checks.registration_checks import submitted_registration_has_been_processed

logger = logging.getLogger(__name__)


@shared_task
def perform_task_in_job():
    logger.info("PERFORM_TASK_IN_JOB")


@shared_task
def check_registrations():
    submitted_registration_has_been_processed()
