release: python manage.py migrate
web: gunicorn ridehub.asgi:application -k uvicorn_worker.UvicornWorker
worker: celery -A ridehub worker -B -S django_celery_beat.schedulers:DatabaseScheduler --concurrency=2 -l INFO
