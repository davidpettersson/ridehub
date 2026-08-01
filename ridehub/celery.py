import os
from urllib.parse import urlparse, parse_qs, urlencode

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ridehub.settings')


def _broker_url() -> str:
    redis_url = os.environ.get('REDIS_URL')

    if not redis_url:
        if 'DYNO' in os.environ:
            raise RuntimeError('REDIS_URL is not set; attach a Redis add-on to this Heroku app')
        redis_url = 'redis://localhost:6379/0'

    if not redis_url.startswith('rediss://'):
        return redis_url

    parsed_url = urlparse(redis_url)
    query_params = parse_qs(parsed_url.query)

    if 'ssl_cert_reqs' in query_params:
        return redis_url

    query_params['ssl_cert_reqs'] = ['CERT_NONE']
    parsed_url = parsed_url._replace(query=urlencode(query_params, doseq=True))
    return parsed_url.geturl()


app = Celery('ridehub')

broker_url = _broker_url()
app.conf.update(broker_url=broker_url, result_backend=broker_url)

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()
