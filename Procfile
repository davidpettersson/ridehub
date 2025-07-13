release: python manage.py migrate
web: gunicorn ridehub.wsgi
worker: celery -A ridehub worker -B -S django_celery_beat.schedulers:DatabaseScheduler -l DEBUG