release: python manage.py migrate
web: gunicorn ridehub.wsgi
worker: celery -A ridehub worker -l DEBUG