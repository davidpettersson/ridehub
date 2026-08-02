import os
from urllib.parse import urlparse, parse_qs, urlencode

LOCAL_REDIS_URL = 'redis://localhost:6379/0'

KOMBU_CERT_NONE = 'CERT_NONE'
REDIS_PY_CERT_NONE = 'none'


def redis_url(cert_reqs: str = KOMBU_CERT_NONE) -> str:
    url = os.environ.get('REDIS_URL')

    if not url:
        if 'DYNO' in os.environ:
            raise RuntimeError('REDIS_URL is not set; attach a Redis add-on to this Heroku app')
        return LOCAL_REDIS_URL

    if not url.startswith('rediss://'):
        return url

    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)

    if 'ssl_cert_reqs' in query_params:
        return url

    query_params['ssl_cert_reqs'] = [cert_reqs]
    parsed_url = parsed_url._replace(query=urlencode(query_params, doseq=True))
    return parsed_url.geturl()


def celery_redis_url() -> str:
    return redis_url(KOMBU_CERT_NONE)


def cache_redis_url() -> str:
    return redis_url(REDIS_PY_CERT_NONE)
