export CELERY_PROTOCOL='amqp'
export CELERY_USER='guest'
export CELERY_PASSWORD='guest'
export QUEUE_HOST='localhost'
export QUEUE_PORT='5672'
gunicorn -b 0.0.0.0:8000 sumstats_service.app:app --log-level=debug
