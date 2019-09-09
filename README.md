# gwas-sumstats-service

[![Codacy Badge](https://api.codacy.com/project/badge/Grade/5d4d969b4a204439a9663cca413c8043)](https://www.codacy.com/app/hayhurst.jd/gwas-sumstats-service?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=EBISPOT/gwas-sumstats-service&amp;utm_campaign=Badge_Grade)
[![Build Status](https://travis-ci.org/EBISPOT/gwas-sumstats-service.svg?branch=master)](https://travis-ci.org/EBISPOT/gwas-sumstats-service)
[![Codacy Badge](https://api.codacy.com/project/badge/Coverage/5d4d969b4a204439a9663cca413c8043)](https://www.codacy.com/app/hayhurst.jd/gwas-sumstats-service?utm_source=github.com&utm_medium=referral&utm_content=EBISPOT/gwas-sumstats-service&utm_campaign=Badge_Coverage)

## GWAS summary statistics service app

This handles the uploaded summary statistics files, validates them, reports errors to the deposition app and puts valid files in the queue for sumstats file harmonisation and HDF5 loading.

- There is a Flask app handling `POST` and `GET` requests via the endpoints below. Celery worker(s) perform the validation tasks in the background. They can work from anywhere the app is installed and can see the RabbitMQ queue. 


## Local installation

- Requires: [RabbitMQ](https://www.rabbitmq.com/) and Python 3.6
- Clone the repository
  - `git clone https://github.com/EBISPOT/gwas-sumstats-service.git`
  - `cd gwas-sumstats-service`
  - Set up environment
  - `virtualenv --python=python3.6 .env`
  - `source activate .env/bin/activate`
- Install
  - `pip install .`
  - `pip install -r requirements.txt`
  
### Run the tests

- Run this, to setup up a RabbitMQ server, run the tests, and tear it all down.
- `tox` 


### Run as a flask app

- Spin up a RabbitMQ server on the port (`BROKER_PORT`) specified in the config e.g.
  - `rabbitmq-server`
- Start the flask app with gunicorn http://localhost:8000
  - from `gwas-sumstats-service`:
  - `gunicorn -b 0.0.0.0:8000 sumstats_service.app:app --log-level=debug`
- Start a celery worker for the database side
  - from `gwas-sumstats-service`:
  - `celery -A sumstats_service.app.celery worker --loglevel=debug --queues=postval`
- Start a celery worker for the validation side
  - from `gwas-sumstats-service`:
  - `celery -A sumstats_service.app.celery worker --loglevel=debug --queues=preval`
 

## Run with Docker-compose
- Spin up the Flask and RabbitMQ and Celery docker containers
  - clone repo as above
  - `docker-compose build`
  - `docker-compose up`
- Start up a celery worker on the machine validating and storing the files
  - follow the local installation as above
  - set `BROKER_HOST` to that of RabbitMQ host e.g. `localhost` in config.py 
  - `celery -A sumstats_service.app.celery worker --queues=preval --loglevel=debug`

## Deploy with helm (kubernetes)
- First, deploy rabbitmq using helm 
  - `helm install --name rabbitmq --set rabbitmq.password=<pwd>,rabbitmq.username=<user>,service.type=NodePort,service.nodePort=<port> stable/rabbitmq`
- deploy the sumstats service
  - `helm install --name gwas-sumstats k8chart/ --wait`
- Start a celery worker from docker
  - `docker run -it -d --name sumstats -v /path/to/data/:$INSTALL_PATH/sumstats_service/data -e CELERY_USER=<user> -e CELERY_PASSWORD=<pwd> -e QUEUE_HOST=<host ip> -e QUEUE_PORT=<port>  gwas-sumstats-service:latest /bin/bash`
  - `docker exec sumstats celery -A sumstats_service.app.celery worker --loglevel=debug --queues=preval`


### Example POST method
```
curl -i -H "Content-Type: application/json" -X POST -d '{"requestEntries":[{"id":"abc123","filePath":"https://raw.githubusercontent.com/EBISPOT/gwas-sumstats-service/master/tests/test_sumstats_file.tsv","md5":"a1195761f082f8cbc2f5a560743077cc","assembly":"38"},{"id":"bcd234","filePath":"https://raw.githubusercontent.com/EBISPOT/gwas-sumstats-service/master/tests/test_sumstats_file.tsv","md5":"a1195761f082f8cbc","assembly":"38"}]}' http://localhost:8000/v1/sum-stats

HTTP/1.0 201 CREATED
Content-Type: application/json
Content-Length: 26
Server: Werkzeug/0.15.4 Python/3.6.5
Date: Wed, 17 Jul 2019 15:15:23 GMT

{"callbackID": "TiQS2yxV"}
```

### Example GET method (using callback id from above)
```
curl http://localhost:8000/v1/sum-stats/TiQS2yxV

{
  "callbackID": "TiQS2yxV",
  "completed": false,
  "statusList": [
    {
      "id": "abc123",
      "status": "VALID",
      "error": null
    },
    {
      "id": "bcd234",
      "status": "INVALID",
      "error": "md5sum did not match the one provided"
    }
  ]
}
```

