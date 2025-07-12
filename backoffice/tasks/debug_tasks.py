from celery import shared_task


@shared_task
def perform_task_in_job():
import logging
from celery import shared_task

logger = logging.getLogger(__name__)

@shared_task
def perform_task_in_job():
    logger.info("PERFORM_TASK_IN_JOB")
