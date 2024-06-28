# gwas-sumstats-service

[![Codacy Badge](https://api.codacy.com/project/badge/Grade/5d4d969b4a204439a9663cca413c8043)](https://www.codacy.com/app/hayhurst.jd/gwas-sumstats-service?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=EBISPOT/gwas-sumstats-service&amp;utm_campaign=Badge_Grade)
[![Build Status](https://travis-ci.org/EBISPOT/gwas-sumstats-service.svg?branch=master)](https://travis-ci.org/EBISPOT/gwas-sumstats-service)
[![Codacy Badge](https://api.codacy.com/project/badge/Coverage/5d4d969b4a204439a9663cca413c8043)](https://www.codacy.com/app/hayhurst.jd/gwas-sumstats-service?utm_source=github.com&utm_medium=referral&utm_content=EBISPOT/gwas-sumstats-service&utm_campaign=Badge_Coverage)

## GWAS summary statistics service app

This handles the uploaded summary statistics files, validates them, reports errors to the deposition app and puts valid files in the queue for sumstats file harmonisation and HDF5 loading.

- There is a Flask app handling `POST` and `GET` requests via the endpoints below. Celery worker(s) perform the validation tasks in the background. They can work from anywhere the app is installed and can see the RabbitMQ queue. 


## Local installation

### Requirements
- Python3.9
- [RabbitMQ](https://www.rabbitmq.com/)
- libmagic (e.g. `brew install libmagic`)
- [mongodb](https://www.mongodb.com/docs/manual/administration/install-community/) and start the mongodb service
- [nextflow](https://www.nextflow.io/docs/latest/getstarted.html#installation)

### Installation
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

- Make sure that the installation is complete.
- Start locally or `docker-compose up`.
- To setup up a RabbitMQ server, run the tests, and tear it all down:
  ```bash
  rm -rf .tox
  tox
  ```

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

This section guides you through using Docker-compose to set up and run the `gwas-sumstats-service` with all necessary services, including Flask, RabbitMQ, Celery, and MongoDB.

### Prerequisites
- Ensure Docker and Docker-compose are installed on your system.
- Clone the repository:
  ```bash
  git clone [repository-url]
  ```

### Steps to Run
0. Replace the local [Dockerfile](./dockerfile.local) and [docker-compose file](./docker-compose.local.yaml) with `Dockerfile` and `docker-compose.yaml`, respectively. 

1. **Build the Docker Containers**
   
   Navigate to the cloned directory and build the Docker containers:
   ```bash
   docker-compose build
   ```

2. **Start the Docker Containers**

   Spin up the Flask, RabbitMQ, Celery, and MongoDB containers:
   ```bash
   docker-compose up
   ```

### Additional Configuration
- Use the `CONTAINERISE` environment variable to adapt the application's behavior accordingly if you require Singularity.
- To debug locally using Docker, update the Dockerfile and local executor configurations in [the config file](./sumstats_service/config.py) as follows.
  ```python
  ...
  NEXTFLOW_CONFIG = (
      # "executor.name = 'slurm'\n"
      # "process.executor = 'slurm'\n"

      "executor.name = 'local'\n"
  ...
  ```

## Deploy with helm (kubernetes)
- First, deploy rabbitmq using helm 
  - `helm install --name rabbitmq --namespace rabbitmq --set rabbitmq.username=<user>,service.type=NodePort,service.nodePort=<port> stable/rabbitmq`
- create kubernetes secrets for the ssh keys and Globus
  - `kubectl --kubeconfig=<path to config> -n <namespace> create secret generic ssh-keys --from-file=id_rsa=<path/to/id_rsa> --from-file=id_rsa.pub=/path/to/id_rsa.pub> --from-file=known_hosts=/path/to/known_hosts`
  - `kubectl --kubeconfig=<path to config> -n gwas create secret generic globus --from-file=refresh-tokens.json=<path/to/refresh-tokens.json>`
- deploy the sumstats service
  - `helm install --name gwas-sumstats k8chart/ --wait`
- Start a celery worker from docker
  - `docker run -it -d --name sumstats -v /path/to/data/:$INSTALL_PATH/sumstats_service/data -e CELERY_USER=<user> -e CELERY_PASSWORD=<pwd> -e QUEUE_HOST=<host ip> -e QUEUE_PORT=<port>  gwas-sumstats-service:latest /bin/bash`
  - `docker exec sumstats celery -A sumstats_service.app.celery worker --loglevel=debug --queues=preval`

## Testing

### Testing with Postman

This section provides instructions on how to test the `gwas-sumstats-service` using Postman. The Postman collection for this service includes requests for submitting summary statistics and retrieving their validation status. Please find the collection [here](./tests/postman/gwas-sumstats-service.postman_collection.json).


#### Pre-requisites

- Ensure you have Postman installed.
- Import the Postman collection `gwas-sumstats-service` (ID: e03dcb59-01cb-411b-a8d0-b216e2860c9f) into your Postman application.

#### Testing Steps

1. **Submit Summary Statistics**

   - Use the `POST {{protocol}}://{{host}}:{{port}}/v1/sum-stats` request to submit summary statistics.
   - Update the `id` field in the request body with a unique identifier. Example body for a valid file submission:
     ```json
     {
       "requestEntries": [
         {
           "id": "{{callbackId}}",
           "filePath": "test_sumstats_file.tsv",
           "md5": "9b5f307016408b70cde2c9342648aa9b",
           "assembly": "GRCh38",
           "readme": "optional text",
           "entryUUID": "ABC1234",
           "minrows": "2"
         }
       ]
     }
     ```
   - For an invalid file submission, modify the `filePath` and other relevant fields accordingly.
   - Note the returned `callbackID` from the response for the next step.

2. **Retrieve Validation Status**

   - Use the `GET {{protocol}}://{{host}}:{{port}}/v1/sum-stats/<callbackID>` request to retrieve the status of your submission.
   - Replace `<callbackID>` with the ID obtained from the previous POST request.
   - The response will indicate the validation status of the submission.

#### Debugging Invalid Submissions

- In case of an invalid submission, access the Docker container's shell as root to inspect the validation logs and output files:
  ```bash
  root@container-id:/sumstats_service# ls depo_ss_validated/<callbackID>/
  ```
  - Check the `nextflow.log` for detailed execution logs:
    ```bash
    root@container-id:/sumstats_service# cat depo_ss_validated/<callbackID>/logs/nextflow.log
    ```

#### Postman Collection Details

- The collection includes two primary requests: `POST sum-stats` for submission and `GET sum-stats` for status retrieval.
- Variables such as `{{protocol}}`, `{{host}}`, and `{{port}}` are pre-defined in the collection for ease of use.
- Each request includes appropriate headers and request bodies as per the API specifications.


### Testing with Curl

#### Example POST method
```
curl -i -H "Content-Type: application/json" -X POST -d '{"requestEntries":[{"id":"abc123","filePath":"https://raw.githubusercontent.com/EBISPOT/gwas-sumstats-service/master/tests/test_sumstats_file.tsv","md5":"a1195761f082f8cbc2f5a560743077cc","assembly":"GRCh38", "readme":"optional text", "entryUUID": "globusdir"},{"id":"bcd234","filePath":"https://raw.githubusercontent.com/EBISPOT/gwas-sumstats-service/master/tests/test_sumstats_file.tsv","md5":"a1195761f082f8cbc","assembly":"GRCh38", "entryUUID": "globusdir"}]}' http://localhost:8000/v1/sum-stats

HTTP/1.0 201 CREATED
Content-Type: application/json
Content-Length: 26
Server: Werkzeug/0.15.4 Python/3.6.5
Date: Wed, 17 Jul 2019 15:15:23 GMT

{"callbackID": "TiQS2yxV"}
```

#### Example GET method (using callback id from above)
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

## Misc - Format and Lint

### Installation

Follow these steps to set up FormatLint:

### 1. Create a Virtual Environment

Create a new virtual environment for the project to manage dependencies separately from your global Python setup:

```bash
python -m venv formatlint
```

Activate the virtual environment:

```bash
source formatlint/bin/activate
```

### 2. Install Dependencies

Install the required Python packages:

```bash
pip install -r requirements.dev.txt
```

### 3. Run FormatLint

Execute the formatting and linting script:

```bash
./format-lint
```