import os

import pytest


@pytest.fixture(scope='session')
def celery_config():
    return {
            'broker_url': '{msg_protocol}://{user}:{pwd}@{host}:{port}//'.format(
                msg_protocol=os.environ['CELERY_PROTOCOL'],
                user=os.environ['CELERY_USER'],
                pwd=os.environ['CELERY_PASSWORD'],
                host=os.environ['QUEUE_HOST'],
                port=os.environ['QUEUE_PORT']
                ),
            'result_backend': 'rpc://',
            'queues':('preval', 'postval', 'metadata-yml-update'),
            'task_always_eager': True
           }

    
