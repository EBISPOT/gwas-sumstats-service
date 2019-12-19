FROM python:3.6-slim-buster

ENV INSTALL_PATH /sumstats_service
RUN mkdir -p $INSTALL_PATH
WORKDIR $INSTALL_PATH

COPY requirements.txt requirements.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc openssh-client python-dev libmagic-dev \
    && rm -rf /var/lib/apt/lists/* \
    && pip install -r requirements.txt \
    && apt-get purge -y --auto-remove gcc python-dev
# the --no-install-recommends helps limit some of the install so that you can be more explicit about what gets installed

COPY . .

RUN pip install -e .

# Expose port:
EXPOSE 8000

RUN mkdir -p logs

ENV CELERY_PROTOCOL "amqp"
ENV CELERY_USER "guest"
ENV CELERY_PASSWORD "guest"
ENV QUEUE_HOST "rabbitmq.rabbitmq"
ENV QUEUE_PORT 5672
ENV STORAGE_PATH "./data"
ENV VALIDATE_WITH_SSH ""
ENV COMPUTE_FARM_LOGIN_NODE ""
ENV COMPUTE_FARM_USERNAME ""
ENV SINGULARITY_IMAGE "ebispot/gwas-sumstats-service"
ENV SINGULARITY_TAG "latest"
ENV HTTP_PROXY ""
ENV HTTPS_PROXY ""
ENV GWAS_ENDPOINT_ID ""
ENV GLOBUS_SECRET ""
ENV TRANSFER_CLIENT_ID ""
ENV CLIENT_ID ""
ENV FTP_SERVER ""
ENV FTP_USERNAME ""
ENV FTP_PASSWORD ""
ENV MONGO_URI ""
ENV MONGO_USER ""
ENV MONGO_PASSWORD ""
ENV MONGO_DB = ""
