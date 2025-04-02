from celery import shared_task

@shared_task
def perform_task_in_job():
    print("PERFORM_TASK_IN_JOB")