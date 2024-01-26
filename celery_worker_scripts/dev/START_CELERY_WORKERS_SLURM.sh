#!/bin/bash

COMMIT_SHA=$1

ENV_FILE="/hps/software/users/parkinso/spot/gwas/dev/scripts/cron/sumstats_service/cel_envs_sandbox"
LOG_LEVEL="info"
MEM="8000"
CLUSTER_QUEUE="standard"

source $ENV_FILE

# Module install cmd
lmod_cmd="module load singularity-3.6.4-gcc-9.3.0-yvkwp5n; module load openjdk-16.0.2-gcc-9.3.0-xyn6nf5; module load nextflow-21.10.6-gcc-9.3.0-tkuemwd"

# pull Singularity image

if [ ! -z "${COMMIT_SHA}" ];
then
    echo "START pulling Singularity Image"
    sed -i "s/SINGULARITY_TAG=.*/SINGULARITY_TAG=\"${COMMIT_SHA}\"/g" $ENV_FILE
    singularity pull --dir $SINGULARITY_CACHEDIR docker://${SINGULARITY_REPO}/${SINGULARITY_IMAGE}:${COMMIT_SHA}
    SINGULARITY_TAG=$COMMIT_SHA
    echo "DONE pulling Singularity Image"
else
    echo "COMMIT_SHA not set"
fi

# Set Singularity cmd
echo "START setting Singularity cmd"
singularity_cmd="singularity exec --env-file $ENV_FILE $SINGULARITY_CACHEDIR/gwas-sumstats-service_${SINGULARITY_TAG}.sif"
echo "DONE setting Singularity cmd"

# Set celery worker cmd
celery_cmd="celery -A sumstats_service.app.celery worker --loglevel=${LOG_LEVEL} --queues=${CELERY_QUEUE1},${CELERY_QUEUE2} > celery_worker_dev.log 2>&1"

# Shutdown gracefully all jobs named sumstats_service_celery_worker
# --full is required because "By default, signals other than SIGKILL 
# are not sent to the batch step (the shell script). With this 
# option scancel also signals the batch script and its children processes."
# See https://slurm.schedmd.com/scancel.html#OPT_full
echo "sending SIGTERM signal to dev celery workers"
scancel --name=sumstats_service_celery_worker --signal=TERM --full

echo "START spinning up dev celery workers:"
# Submit new SLURM jobs for celery workers
for WORKER_ID in {1..2}; do
    echo $WORKER_ID
    sbatch --parsable --output="cel_${WORKER_ID}.o" --error="cel_${WORKER_ID}.e" --mem=${MEM} --time=7-00:00:00 --job-name=sumstats_service_celery_worker --wrap="${lmod_cmd}; ${singularity_cmd} ${celery_cmd}"
done
echo "DONE spinning up dev celery workers"
