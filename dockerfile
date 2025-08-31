# ---- Build curl with c-ares (no threaded resolver) ----
FROM debian:bookworm-slim AS curl-build
ARG CURL_VER=8.8.0
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential autoconf automake libtool pkg-config \
      curl libssl-dev zlib1g-dev libzstd-dev libidn2-0-dev libpsl-dev \
      libnghttp2-dev libssh2-1-dev libbrotli-dev libc-ares-dev \
  && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://curl.se/download/curl-${CURL_VER}.tar.xz | tar -xJ && \
    cd curl-${CURL_VER} && \
    ./configure --with-ssl --with-brotli --with-zstd --with-nghttp2 --enable-ares --disable-ldap --prefix=/usr/local && \
    make -j"$(nproc)" && make install-strip

# --- Final runtime image ---
FROM python:3.9-slim-bookworm
# Need to compatible with GLIBC 2.36 since slurm 24.11.5 requires 2.34 

RUN groupadd -r sumstats-service && useradd -r --create-home -g sumstats-service sumstats-service

ENV INSTALL_PATH=/sumstats_service \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NO_PROXY=localhost,127.0.0.1,.svc,.svc.cluster.local,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16
ENV no_proxy=${NO_PROXY}

RUN mkdir -p $INSTALL_PATH
WORKDIR $INSTALL_PATH

COPY requirements.txt requirements.txt
RUN set -eux \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates \
       libc-ares2 libnghttp2-14 libssh2-1 libpsl5 libidn2-0 libbrotli1 libzstd1 zlib1g libssl3 \
       openssh-client libmagic-dev \
       procps \
       dnsutils \
       iputils-ping \
    && apt-get install -y --no-install-recommends \
       gcc \
       build-essential \
       python3-dev \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --upgrade pip \
    && pip install -r requirements.txt \
    && apt-get purge -y --auto-remove gcc python3-dev build-essential 
# the --no-install-recommends helps limit some of the install so that you can be more explicit about what gets installed

# drop in the c-ares-enabled curl
COPY --from=curl-build /usr/local/bin/curl /usr/local/bin/curl
COPY --from=curl-build /usr/local/lib/libcurl.so* /usr/local/lib/

# prove curl has AsynchDNS at build-time
RUN curl -V | grep -q AsynchDNS

COPY . .

RUN pip install -e .

# Expose port:
EXPOSE 8000

RUN mkdir -p logs
RUN chown -R sumstats-service:sumstats-service $INSTALL_PATH

ENV CELERY_PROTOCOL "amqp"
ENV CELERY_USER "guest"
ENV CELERY_PASSWORD "guest"
ENV QUEUE_HOST "rabbitmq.rabbitmq"
ENV QUEUE_PORT 5672
ENV CELERY_QUEUE1 "preval"
ENV CELERY_QUEUE2 "postval"
ENV STORAGE_PATH "./data"
ENV STAGING_PATH "./staging"
ENV DEPO_PATH "./depo_data"
ENV VALIDATED_PATH "./depo_ss_validated"
ENV SW_PATH "./bin"
ENV VALIDATE_WITH_SSH ""
ENV COMPUTE_FARM_LOGIN_NODE ""
ENV COMPUTE_FARM_USERNAME ""
ENV COMPUTE_FARM_QUEUE_LONG ""
ENV SINGULARITY_IMAGE "ebispot/gwas-sumstats-service"
ENV SINGULARITY_TAG "latest"
ENV SINGULARITY_CACHEDIR ""
ENV REMOTE_HTTP_PROXY ""
ENV REMOTE_HTTPS_PROXY ""
ENV GWAS_ENDPOINT_ID ""
ENV CLIENT_SECRET ""
ENV TRANSFER_CLIENT_ID ""
ENV GWAS_GLOBUS_GROUP ""
ENV CLIENT_ID ""
ENV GLOBUS_HOSTNAME ""
ENV MAPPED_COLLECTION_ID ""
ENV STORAGE_GATEWAY_ID ""
ENV FTP_SERVER ""
ENV FTP_USERNAME ""
ENV FTP_PASSWORD ""
ENV MONGO_URI ""
ENV MONGO_USER ""
ENV MONGO_PASSWORD ""
ENV MONGO_DB ""
ENV HTTP_PROXY ""
ENV HTTPS_PROXY ""
ENV no_proxy "localhost,.cluster.local"
ENV DEPO_API_AUTH_TOKEN ""
ENV OUTPUT_PATH "metadata/output"
ENV SUMSTATS_FILE_TYPE ""
ENV GWAS_DEPO_REST_API_URL ""

USER sumstats-service
