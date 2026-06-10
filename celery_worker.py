# ============================================================
# FILE: celery_worker.py
# PURPOSE: Celery worker entry point
# RUN LOCALLY: celery -A celery_worker.celery worker --loglevel=info
# RUN BEAT:    celery -A celery_worker.celery beat --loglevel=info
# NOTE: Two separate Railway services required in production:
#       Service 1 (Web): gunicorn app:app
#       Service 2 (Worker): celery -A celery_worker.celery worker
# ============================================================

import os
from celery import Celery
from app import create_app

flask_app = create_app()

celery = Celery(
    flask_app.import_name,
    broker=os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
    backend=os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
)

celery.config_from_object('app.celery_config')


class ContextTask(celery.Task):
    """Makes every Celery task run inside Flask application context."""
    def __call__(self, *args, **kwargs):
        with flask_app.app_context():
            return self.run(*args, **kwargs)


celery.Task = ContextTask
