FROM python:3.9-slim-buster as builder

RUN groupadd -r sumstats-service && useradd -r --create-home -g sumstats-service sumstats-service

ENV INSTALL_PATH /sumstats_service
WORKDIR $INSTALL_PATH

COPY requirements.txt .
RUN apt-get update \
    && apt-mark hold libc6 libexpat1 \
    && apt-get install -y --no-install-recommends libpython-dev python2.7-dev gcc python-dev libmagic-dev \
    && pip install --upgrade pip \
    && pip install -r requirements.txt \
    && apt-get purge -y --auto-remove gcc python-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

FROM python:3.9-slim-buster as runtime

COPY --from=builder /usr/local /usr/local
COPY --from=builder /sumstats_service /sumstats_service
COPY --from=builder /etc/passwd /etc/group /etc/

WORKDIR /sumstats_service

COPY . .

RUN pip install -e .

EXPOSE 8000

ENV CELERY_PROTOCOL="amqp" \
    CELERY_USER="guest" \
    CELERY_PASSWORD="guest" \
    QUEUE_HOST="rabbitmq.rabbitmq" \
    QUEUE_PORT=5672 \
    CELERY_QUEUE1="preval" \
    CELERY_QUEUE2="postval" \
    STORAGE_PATH="./data" \
    STAGING_PATH="./staging" \
    DEPO_PATH="./depo_data" \
    VALIDATED_PATH="./depo_ss_validated" \
    SW_PATH="./bin" \
    VALIDATE_WITH_SSH="" \
    COMPUTE_FARM_LOGIN_NODE="" \
    COMPUTE_FARM_USERNAME="" \
    COMPUTE_FARM_QUEUE_LONG="" \
    SINGULARITY_IMAGE="ebispot/gwas-sumstats-service" \
    SINGULARITY_TAG="latest" \
    SINGULARITY_CACHEDIR="" \
    REMOTE_HTTP_PROXY="" \
    REMOTE_HTTPS_PROXY="" \
    GWAS_ENDPOINT_ID="" \
    CLIENT_SECRET="" \
    TRANSFER_CLIENT_ID="" \
    GWAS_GLOBUS_GROUP="" \
    CLIENT_ID="" \
    GLOBUS_HOSTNAME="" \
    MAPPED_COLLECTION_ID="" \
    STORAGE_GATEWAY_ID="" \
    FTP_SERVER="" \
    FTP_USERNAME="" \
    FTP_PASSWORD="" \
    MONGO_URI="" \
    MONGO_USER="" \
    MONGO_PASSWORD="" \
    MONGO_DB="" \
    HTTP_PROXY="" \
    HTTPS_PROXY="" \
    no_proxy="localhost,.cluster.local" \
    DEPO_API_AUTH_TOKEN="" \
    OUTPUT_PATH="metadata/output" \
    SUMSTATS_FILE_TYPE="" \
    GWAS_DEPO_REST_API_URL=""

USER sumstats-service