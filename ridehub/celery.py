import os
from urllib.parse import urlparse, parse_qs, urlencode

from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ridehub.settings')

app = Celery('ridehub')

redis_url = os.environ.get('REDIS_URL', 'redis://')

# If using rediss:// (SSL), add the required ssl_cert_reqs parameter if not present
if redis_url.startswith('rediss://'):
    parsed_url = urlparse(redis_url)
    query_params = parse_qs(parsed_url.query)

    # Only add ssl_cert_reqs if it's not already present
    if 'ssl_cert_reqs' not in query_params:
        query_params['ssl_cert_reqs'] = ['CERT_NONE']

        # Rebuild the URL with the added parameter
        new_query = urlencode(query_params, doseq=True)
        parsed_url = parsed_url._replace(query=new_query)

        # Convert back to string
        redis_url = parsed_url.geturl()

# Basic Redis config
app.conf.update(broker_url=redis_url, result_backend=redis_url)

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()
