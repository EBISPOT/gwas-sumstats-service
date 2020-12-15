import json
from urllib.parse import unquote
from flask import url_for
import config
import subprocess
from sumstats_service.resources.error_classes import *
import sumstats_service.resources.payload as pl
import sumstats_service.resources.study_service as st
import sumstats_service.resources.validate_payload as vp
import sumstats_service.resources.ssh_client as sshc
import os
from pathlib import Path
import time
import glob
import logging


logging.basicConfig(level=logging.DEBUG, format='(%(levelname)s): %(message)s')
logger = logging.getLogger(__name__)


def create_href(method_name, params=None):
    params = params or {}
    params['_external'] = True
    return {'href': unquote(
        url_for(method_name, **params)
    )}

def json_payload_to_db(content, callback_id=None):
    payload = pl.Payload(payload=content, callback_id=callback_id)
    payload.payload_to_db()
    if len(payload.metadata_errors) != 0:
        return False
    return payload.callback_id

def generate_callback_id():
    payload = pl.Payload()
    payload.generate_callback_id()
    return payload.callback_id
    

def store_validation_results_in_db(validation_response):
    valid = True
    for item in json.loads(validation_response)['validationList']:
        study_id = item["id"]
        study = st.Study(study_id)
        study.retrieved = item["retrieved"]
        study.data_valid = item["dataValid"]
        study.error_code = item["errorCode"]
        study.store_validation_statuses()
        if study.error_code:
            valid = False
    if valid == False:
        callback_id = json.loads(validation_response)['callbackID']
        payload = pl.Payload(callback_id=callback_id)
        payload.clear_validated_files()



def validate_files_from_payload(callback_id, content, minrows=None):
    validate_metadata = vp.validate_metadata_for_payload(callback_id, content)
    if any([i['errorCode'] for i in json.loads(validate_metadata)['validationList']]):
        #metadata invalid stop here
        return validate_metadata

    par_dir = os.path.join(config.STORAGE_PATH, callback_id)
    payload_path = os.path.join(par_dir, "payload.json")
    nextflow_config_path = os.path.join(par_dir, "nextflow.config")
    log_dir = os.path.join(config.STORAGE_PATH, 'logs', callback_id)
    nextflow_cmd = nextflow_command_string(callback_id, payload_path, log_dir, par_dir, minrows, nextflow_config_path)
    if config.VALIDATE_WITH_SSH == 'true':
        logger.debug('Validate with ssh')
        ssh = sshc.SSHClient(host=config.COMPUTE_FARM_LOGIN_NODE, username=config.COMPUTE_FARM_USERNAME)
        ssh.mkdir(par_dir)
        ssh.write_data_to_file(json.dumps(content), payload_path)
        ssh.write_data_to_file(config.NEXTFLOW_CONFIG, nextflow_config_path)
        memory = 2400
        ssh.write_data_to_file(json.dumps(content), payload_path)
        logger.info('content:\n{}'.format(content))
        command = ssh_command_string(par_dir, log_dir, memory, nextflow_cmd)
        logger.info('command:\n{}'.format(command))
        stdin, stdout, stderr = ssh.exec_command(command)
        jobid = ssh.parse_jobid(stdout)
        logger.info('jobid[]:\n'.format(jobid))
        contents_list = None
        results = None
        if jobid is None:
            print("command didn't return a jobid")
        else:
            while not results: 
                time.sleep(30) # 30 second poll 
                status = ssh.get_job_status(jobid)
                if status in ['DONE', 'EXIT']:
                    file_contents = ssh.get_file_content(os.path.join(par_dir, '[!payload]*.json'))
                    contents_list = file_contents.replace('}{', '}|{').split('|') if len(f) > 0 else False
                if status in ['PEND', 'RUN']:
                    continue
                else:
                    print(status)
                    break
        if contents_list is True:
            contents_list_of_dicts = [json.loads(i) for i in contents_list]
            results = {
                    "callbackID": callback_id,
                    "validationList" : contents_list_of_dicts
                  }
            results = add_errors_if_study_missing(callback_id, content, results)
        else:
            results = results_if_failure(callback_id, content)
        ssh.rm(par_dir, callback_id)
        ssh.close_connection()
        logger.info(results)
        return json.dumps(results)
    else:
        logger.debug('Validate without ssh')
        return validate_files_NOT_SSH(callback_id, content, par_dir, payload_path, nextflow_config_path, log_dir, nextflow_cmd)

    
def add_errors_if_study_missing(callback_id, content, results):
    if any([s['errorCode'] for s in results['validationList']]):
        # if we already identfied errors, there's no need to add them
        return results
    else:
        payload = pl.Payload(callback_id=callback_id, payload=content)
        payload.create_study_obj_list()
        study_list = [s.study_id for s in payload.study_obj_list]
        studies_with_results = [s['id'] for s in results['validationList']]
        for study in study_list:
            if study not in studies_with_results:
                results['validationList'].append({"id": study, "retrieved": None, "dataValid": None, "errorCode": 10})
        return results
            
    
def validate_files_NOT_SSH(callback_id, content, par_dir, payload_path, nextflow_config_path, log_dir, nextflow_cmd):
    # maintain this for the sandbox which cannot ssh ebi farm
    logger.debug('Validate without ssh')
    Path(par_dir).mkdir(parents=True, exist_ok=True)
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    with open(payload_path, 'w') as f:
        f.write(json.dumps(content))
    with open(nextflow_config_path, 'w') as f:
        f.write(config.NEXTFLOW_CONFIG)
    pipe_ps = subprocess.run(nextflow_cmd.split())
    logger.debug('pipeline process output:\n{}'.format(pipe_ps))
    json_out_files = glob.glob(os.path.join(par_dir, '[!payload]*.json'))
    results = {
                "callbackID": callback_id,
                "validationList" : []
              }
    if len(json_out_files) > 0:
        for j in json_out_files:
            with open(j, 'r') as f:
                results["validationList"].append(json.load(f))
        add_errors_if_study_missing(callback_id, content, results)
    else:
        results = results_if_failure(callback_id, content)
    logger.info(json.dumps(results))
    remove_payload_files(callback_id)
    return json.dumps(results)


def results_if_failure(callback_id, content):
    payload = pl.Payload(callback_id=callback_id, payload=content)
    payload.create_study_obj_list()
    results = vp.construct_failure_response(callback_id, payload)
    return results


def nextflow_command_string(callback_id, payload_path, log_dir, par_dir, minrows, nextflow_config_path):
    nextflow_cmd =  """
                    nextflow -log {logs}/nextflow.log \
                            run validate_submission.nf \
                            --payload {plp} \
                            --storePath {sp} \
                            --cid {cid} \
                            --ftpServer {ftps} \
                            --ftpUser {ftpu} \
                            --ftpPWD {ftpp} \
                            --minrows {mr} \
                            --validatedPath {vp} \
                            -w {wd} \
                            -c {conf} \
                            -with-singularity docker://{image}:{tag}
                    """.format(image=config.SINGULARITY_IMAGE, 
                            tag=config.SINGULARITY_TAG, 
                            cid=callback_id, 
                            sp=config.STORAGE_PATH, 
                            vp=config.VALIDATED_PATH, 
                            ftps=config.FTP_SERVER, 
                            ftpu=config.FTP_USERNAME, 
                            ftpp=config.FTP_PASSWORD, 
                            plp=payload_path,
                            logs=log_dir,
                            wd=par_dir,
                            mr=minrows,
                            conf=nextflow_config_path)
    return nextflow_cmd

def ssh_command_string(par_dir, log_dir, memory, nextflow_cmd):
    command = ("export http_proxy={hp}; "
               "export https_proxy={hsp}; "
               "export VALIDATE_WITH_SSH={ssh}; "
               "export PATH=$PATH:{sw}; "
               "mkdir -p {logs}; "
               "bsub -oo {logs}/stdout -eo {logs}/stderr "
               "-M {mem} -R 'rusage[mem={mem}]' "
               "'{nextflow_cmd}'").format(
                    pd=par_dir, 
                    q=config.COMPUTE_FARM_QUEUE, 
                    logs=log_dir,
                    sw=config.SW_PATH,
                    mem=memory, 
                    nextflow_cmd=nextflow_cmd, 
                    hp=config.REMOTE_HTTP_PROXY, 
                    hsp=config.REMOTE_HTTPS_PROXY, 
                    ssh=config.VALIDATE_WITH_SSH
                    )
    return command


def validate_metadata(callback_id):
    metadata_valid = []
    payload = pl.Payload(callback_id=callback_id)    
    payload.get_data_for_callback_id()
    for study in payload.study_obj_list:
        metadata_valid.append(study.validate_metadata())
    if any(metadata_valid) == False:
        return False
    else:
        return True


def delete_payload_from_db(callback_id):
    payload = pl.Payload(callback_id=callback_id)
    if not payload:
        raise RequestedNotFound("Couldn't find resource with callback id: {}".format(self.callback_id))
    payload.get_data_for_callback_id()
    payload.remove_callback_id()
    status_list = []
    for study in payload.study_obj_list:
        status_list.append({
                            "id": study.study_id, 
                            "status": "DELETED"
                            })
        study.remove()
    response = {"callbackID": str(callback_id),
                "status": "DELETED",
                "statusList": status_list
                }
    return json.dumps(response)


def remove_payload_files(callback_id):
    payload = pl.Payload(callback_id=callback_id)
    payload.remove_payload_directory()


def publish_sumstats(study_list):
    for s in study_list['studyList']:
        study = st.Study(study_id=s['id'], file_path=s['file_path'],
                        assembly=s['assembly'], callback_id=s['callback_id'],
                        readme=s['readme'], entryUUID=s['entryUUID'],
                        author_name=s['author_name'], pmid=s['pmid'], gcst=s['gcst'])
        study.move_file_to_staging()


def construct_get_payload_response(callback_id):
    response = None
    payload = pl.Payload(callback_id=callback_id)
    if payload.get_data_for_callback_id():
        if not payload.study_obj_list:
            # callback registered but studies not yet added (due to async)
            response = {"callbackID": str(callback_id),
                        "status": "PROCESSING"}
            if payload.metadata_errors:
                response["metadataErrors"] = payload.metadata_errors
                response["status"] = "INVALID"
        else:
            payload_status = payload.get_payload_status()
            status_list = []
            for study in payload.study_obj_list:
                study_report = create_study_report(study)
                status_list.append(study_report)
            response = {"callbackID": str(callback_id),
                        "status": payload_status,
                        "statusList": status_list
                        }
    return response


def update_payload(callback_id, content):
    payload = pl.Payload(callback_id=callback_id)
    payload.get_data_for_callback_id()
    payload.update_publication_details(content)
    study_list = []
    for study in payload.study_obj_list:
        study_report = {
                        "id": study.study_id,
                        "gcst": study.gcst,
                        "pmid": study.pmid,
                        "file_path": study.file_path,
                        "assembly": study.assembly,
                        "callback_id": study.callback_id,
                        "readme": study.readme,
                        "entryUUID": study.entryUUID,
                        "author_name": study.author_name
                       }
        study_list.append(study_report)
    response = {"callbackID": str(callback_id),
                "studyList": study_list}
    return response


def create_study_report(study):
    report = {
              "id": study.study_id,
              "status": study.get_status(),
              "error": study.get_error_report(),
              "gcst": study.get_gcst()
              }
    return report
