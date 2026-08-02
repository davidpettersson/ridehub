import os

from celery import Celery

from ridehub.redis_url import celery_redis_url

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ridehub.settings')

app = Celery('ridehub')

broker_url = celery_redis_url()
app.conf.update(broker_url=broker_url, result_backend=broker_url)

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()
