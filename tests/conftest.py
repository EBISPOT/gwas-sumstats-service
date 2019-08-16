import pytest


@pytest.fixture(scope='session')
def celery_config():
    return {
            'broker_url': 'amqp://guest@localhost:5682',
            'result_backend': 'rpc://',
            'queues':('preval', 'postval')
           }
