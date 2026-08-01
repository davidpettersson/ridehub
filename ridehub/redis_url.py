import os
from urllib.parse import urlparse, parse_qs, urlencode

LOCAL_REDIS_URL = 'redis://localhost:6379/0'


def redis_url() -> str:
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

    query_params['ssl_cert_reqs'] = ['CERT_NONE']
    parsed_url = parsed_url._replace(query=urlencode(query_params, doseq=True))
    return parsed_url.geturl()
