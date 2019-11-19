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
