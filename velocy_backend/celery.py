import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'velocy_backend.settings')  # replace with your project name

app = Celery('velocy_backend')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
