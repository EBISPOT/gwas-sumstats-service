#!/bin/bash


ENV_FILE="/hps/software/users/parkinso/spot/gwas/prod/scripts/cron/sumstats_service/cel_envs_hx"
LOG_LEVEL="info"
MEM="8000"
CLUSTER_QUEUE="standard"

source $ENV_FILE

# Module install cmd
lmod_cmd="module load singularity-3.6.4-gcc-9.3.0-yvkwp5n; module load openjdk-16.0.2-gcc-9.3.0-xyn6nf5; module load nextflow-21.10.6-gcc-9.3.0-tkuemwd"

# pull Singularity image

singularity pull --dir $SINGULARITY_CACHEDIR --force  docker://${SINGULARITY_REPO}/${SINGULARITY_IMAGE}:latest

# Set Singularity cmd
singularity_cmd="singularity exec --env-file $ENV_FILE $SINGULARITY_CACHEDIR/gwas-sumstats-service_latest.sif"

# Set celery worker cmd
celery_cmd="celery -A sumstats_service.app.celery worker --loglevel=${LOG_LEVEL} --queues=${CELERY_QUEUE1},${CELERY_QUEUE2},${CELERY_QUEUE3}"


# Warm shutdown existing celery workers
bkill -g /depo_validation_prod 0

# Submit new celery workers
echo "spinning up HX celery workers:"
for WORKER_ID in {1..3}; do
	echo $WORKER_ID
	bsub -g /depo_validation_prod -oo "cel_${WORKER_ID}.o" -eo "cel_${WORKER_ID}.e" -q ${CLUSTER_QUEUE} -M ${MEM} -R "rusage[mem=${MEM}]" "${lmod_cmd}; ${singularity_cmd} ${celery_cmd}"
done

# spin up the workers for hl rabbitmq
ENV_FILE="/hps/software/users/parkinso/spot/gwas/prod/scripts/cron/sumstats_service/cel_envs_hh"
singularity_cmd="singularity exec --env-file $ENV_FILE $SINGULARITY_CACHEDIR/gwas-sumstats-service_latest.sif"

echo "spinning up HH celery workers:"
for WORKER_ID in {4..6}; do
	echo $WORKER_ID
        bsub -g /depo_validation_prod -oo "cel_${WORKER_ID}.o" -eo "cel_${WORKER_ID}.e" -q ${CLUSTER_QUEUE} -M ${MEM} -R "rusage[mem=${MEM}]" "${lmod_cmd}; ${singularity_cmd} ${celery_cmd}"
done
