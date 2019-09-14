export CELERY_PROTOCOL='amqp'
export CELERY_USER='guest'
export CELERY_PASSWORD='guest'
export QUEUE_HOST='localhost'
export QUEUE_PORT='5672'
celery -A sumstats_service.app.celery worker --loglevel=debug --queues=postval,preval

