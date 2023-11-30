#!/bin/bash

ENV_FILE="/hps/software/users/parkinso/spot/gwas/prod/scripts/cron/sumstats_service/cel_envs_hx"
LOG_LEVEL="info"
MEM="8000"
CLUSTER_QUEUE="standard"

source $ENV_FILE

# Module install cmd
lmod_cmd="module load singularity-3.6.4-gcc-9.3.0-yvkwp5n; module load openjdk-16.0.2-gcc-9.3.0-xyn6nf5; module load nextflow-21.10.6-gcc-9.3.0-tkuemwd"

# pull Singularity image
echo "START pulling Singularity Image"
singularity pull --dir $SINGULARITY_CACHEDIR --force  docker://${SINGULARITY_REPO}/${SINGULARITY_IMAGE}:latest
echo "DONE pulling Singularity Image"

# Set Singularity cmd
singularity_cmd="singularity exec --env-file $ENV_FILE $SINGULARITY_CACHEDIR/gwas-sumstats-service_latest.sif"

# Set celery worker cmd
celery_cmd="celery -A sumstats_service.app.celery worker --loglevel=${LOG_LEVEL} --queues=${CELERY_QUEUE1},${CELERY_QUEUE2}"

# Shutdown gracefully all jobs named sumstats_service_celery_worker
# --full is required because "By default, signals other than SIGKILL 
# are not sent to the batch step (the shell script). With this 
# option scancel also signals the batch script and its children processes."
# See https://slurm.schedmd.com/scancel.html#OPT_full
echo "sending SIGTERM signal to prod celery workers"
scancel --name=sumstats_service_celery_worker_prod --signal=TERM --full

# Submit new SLURM jobs for HX celery workers
echo "START spinning up HX celery workers:"
for WORKER_ID in {1..3}; do
	echo $WORKER_ID
    sbatch --parsable --output="cel_${WORKER_ID}.o" --error="cel_${WORKER_ID}.e" --mem=${MEM} --time=7-00:00:00 --job-name=sumstats_service_celery_worker_prod --wrap="${lmod_cmd}; ${singularity_cmd} ${celery_cmd}"
done
echo "DONE spinning up HX celery workers"

# spin up the workers for hl rabbitmq
ENV_FILE="/hps/software/users/parkinso/spot/gwas/prod/scripts/cron/sumstats_service/cel_envs_hh"
singularity_cmd="singularity exec --env-file $ENV_FILE $SINGULARITY_CACHEDIR/gwas-sumstats-service_latest.sif"

# Submit new SLURM jobs for HH celery workers
echo "spinning up HH celery workers:"
for WORKER_ID in {4..6}; do
	echo $WORKER_ID
    sbatch --parsable --output="cel_${WORKER_ID}.o" --error="cel_${WORKER_ID}.e" --mem=${MEM} --time=7-00:00:00 --job-name=sumstats_service_celery_worker_prod --wrap="${lmod_cmd}; ${singularity_cmd} ${celery_cmd}"
done
echo "DONE spinning up HH celery workers"
