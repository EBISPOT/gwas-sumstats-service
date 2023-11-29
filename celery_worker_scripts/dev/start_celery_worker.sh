#!/bin/bash

ENV_FILE="/hps/software/users/parkinso/spot/gwas/dev/scripts/cron/sumstats_service/cel_envs_sandbox"
LOG_LEVEL="info"
MEM="8000"
CLUSTER_QUEUE="standard"

source $ENV_FILE

# Module install cmd
lmod_cmd="module load singularity-3.6.4-gcc-9.3.0-yvkwp5n; module load openjdk-16.0.2-gcc-9.3.0-xyn6nf5; module load nextflow-21.10.6-gcc-9.3.0-tkuemwd"

# Set Singularity cmd
singularity_cmd="singularity exec --env-file $ENV_FILE $SINGULARITY_CACHEDIR/gwas-sumstats-service_${SINGULARITY_TAG}.sif"

# Set celery worker cmd
celery_cmd="celery -A sumstats_service.app.celery worker --loglevel=${LOG_LEVEL} --queues=${CELERY_QUEUE1},${CELERY_QUEUE2}"

# Warm shutdown existing celery workers
bkill -g /depo_validation 0

# Submit new celery workers
for WORKER_ID in {1..2}; do
	bsub -g /depo_validation -oo "cel_${WORKER_ID}.o" -eo "cel_${WORKER_ID}.e" -q ${CLUSTER_QUEUE} -M ${MEM} -R "rusage[mem=${MEM}]" "${lmod_cmd}; ${singularity_cmd} ${celery_cmd}"
done
