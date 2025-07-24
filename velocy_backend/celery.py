import os
from celery import Celery
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'velocy_backend.settings')

app = Celery('velocy_backend')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# Optimize Redis connection pool
app.conf.broker_pool_limit = 20  # Increase connection pool size
app.conf.broker_connection_timeout = 10  # Reduce connection timeout
app.conf.broker_connection_retry = True  # Enable connection retry
app.conf.broker_connection_max_retries = 3  # Limit retries

# Task specific settings
app.conf.task_default_queue = 'default'
app.conf.task_acks_late = True  # Ack after task succeeds
app.conf.task_reject_on_worker_lost = True  # Requeue if worker dies
app.conf.task_track_started = True  # Track task status