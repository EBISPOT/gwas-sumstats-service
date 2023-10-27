FROM python:3.9-slim-buster

RUN groupadd -r sumstats-service && useradd -r --create-home -g sumstats-service sumstats-service

ENV INSTALL_PATH /sumstats_service
RUN mkdir -p $INSTALL_PATH
WORKDIR $INSTALL_PATH

COPY requirements.txt requirements.txt
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        openssh-client \
        python-dev \
        libmagic-dev make \
        curl \
        default-jre \
        build-essential \
        libssl-dev \
        uuid-dev \
        libgpgme11-dev \
        squashfs-tools \
        libseccomp-dev \
        wget \
        pkg-config \
        git \
        cryptsetup \
        qemu-user-static \   
        autoconf \
        automake \
        libfuse-dev \
        libglib2.0-dev \
        libtool \
        runc \
        uidmap \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --upgrade pip \
    && pip install -r requirements.txt
# the --no-install-recommends helps limit some of the install so that you can be more explicit about what gets installed

# # Install Nextflow
# USER root
RUN curl -s https://get.nextflow.io | bash && \
    mv nextflow /usr/local/bin && \
    chmod 777 /usr/local/bin/nextflow

# RUN chmod 777 /usr/local/bin/nextflow

# Installing Go
ENV VERSION=1.21.0
ENV OS=linux
ENV ARCH=arm64
RUN wget https://dl.google.com/go/go$VERSION.$OS-$ARCH.tar.gz && \
    tar -C /usr/local -xzvf go$VERSION.$OS-$ARCH.tar.gz && \
    rm go$VERSION.$OS-$ARCH.tar.gz

# Setting GOPATH and PATH for Go
# RUN echo 'export PATH=/usr/local/go/bin:$PATH' >> ~/.bashrc
ENV PATH="/usr/local/go/bin:${PATH}"

# Install as root
# USER root

# Install Singularity
RUN VERSION_SING=4.0.0 && \
    wget https://github.com/sylabs/singularity/releases/download/v4.0.0/singularity-ce-4.0.0.tar.gz && \
    tar -xzf singularity-ce-4.0.0.tar.gz && \
    cd singularity-ce-4.0.0 && \
    ./mconfig && \
    make -C builddir && \
    make -C builddir install

# Switch back to usual user
# USER sumstats-service

# RUN wget https://github.com/apptainer/singularity/releases/download/v3.8.5/singularity-3.8.5.tar.gz
# RUN tar -xzf singularity-3.8.5.tar.gz
# WORKDIR singularity-3.8.5
# RUN ./mconfig > mconfig.log 2>&1
# RUN cat mconfig.log

COPY . .
COPY ./sumstats_service /sumstats_service
COPY ./tests /tests

RUN pip install -e .

# Expose port:
EXPOSE 8000

RUN mkdir -p logs
RUN chown -R sumstats-service:sumstats-service $INSTALL_PATH

ENV CELERY_PROTOCOL "amqp"
ENV CELERY_USER "guest"
ENV CELERY_PASSWORD "guest"
ENV QUEUE_HOST "rabbitmq"
ENV QUEUE_PORT 5672
ENV CELERY_QUEUE1 "preval"
ENV CELERY_QUEUE2 "postval"
ENV STORAGE_PATH "/sumstats_service/data"
ENV STAGING_PATH "/sumstats_service/staging"
ENV DEPO_PATH "/sumstats_service/depo_data"
ENV TEST_PATH = "/sumstats_service/tests"
ENV VALIDATED_PATH "/sumstats_service/depo_ss_validated"
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

CMD ["flask", "run", "--host=0.0.0.0", "--port=8000"]
