import os
from unittest.mock import patch

import redis
from django.test import TestCase

from ridehub.redis_url import LOCAL_REDIS_URL, cache_redis_url, celery_redis_url


class RedisUrlTests(TestCase):

    def test_falls_back_to_localhost_off_heroku(self):
        # Act
        with patch.dict(os.environ, {}, clear=True):
            url = celery_redis_url()

        # Assert
        self.assertEqual(url, LOCAL_REDIS_URL)

    def test_raises_on_a_dyno_without_redis(self):
        # Act / Assert
        with patch.dict(os.environ, {'DYNO': 'web.1'}, clear=True):
            with self.assertRaises(RuntimeError):
                celery_redis_url()

    def test_plain_redis_url_is_left_alone(self):
        # Act
        with patch.dict(os.environ, {'REDIS_URL': 'redis://localhost:6379/0'}, clear=True):
            url = celery_redis_url()

        # Assert
        self.assertEqual(url, 'redis://localhost:6379/0')

    def test_celery_url_uses_the_flag_spelling_kombu_accepts(self):
        # Act
        with patch.dict(os.environ, {'REDIS_URL': 'rediss://h:pw@example.com:1234'}, clear=True):
            url = celery_redis_url()

        # Assert
        self.assertIn('ssl_cert_reqs=CERT_NONE', url)

    def test_cache_url_is_accepted_by_redis_py(self):
        # Arrange
        with patch.dict(os.environ, {'REDIS_URL': 'rediss://h:pw@example.com:1234'}, clear=True):
            url = cache_redis_url()

        # Act
        pool = redis.ConnectionPool.from_url(url)
        connection = pool.make_connection()

        # Assert
        self.assertIsNotNone(connection)

    def test_an_explicit_flag_in_the_url_is_preserved(self):
        # Act
        with patch.dict(os.environ, {'REDIS_URL': 'rediss://h:pw@example.com:1234?ssl_cert_reqs=required'}, clear=True):
            url = cache_redis_url()

        # Assert
        self.assertIn('ssl_cert_reqs=required', url)
