import json
from urllib.parse import unquote
from flask import url_for
from sumstats_service import config
import subprocess
from sumstats_service.resources.error_classes import *
import sumstats_service.resources.payload as pl
import sumstats_service.resources.study_service as st
import sumstats_service.resources.validate_payload as vp
import sumstats_service.resources.ssh_client as sshc
import sumstats_service.resources.globus as globus
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
        """
        TODO: reinstate globus permissions
        """
        #reinstate_globus_permissions(globus_uuid)
        callback_id = json.loads(validation_response)['callbackID']
        payload = pl.Payload(callback_id=callback_id)
        payload.remove_payload_directory()


def delete_globus_endpoint(globus_uuid):
    status = globus.remove_endpoint_and_all_contents(globus_uuid)
    return status

def reinstate_globus_permissions(globus_uuid):
    pass

def restrict_globus_permissions(globus_uuid):
    pass

def validate_files_from_payload(callback_id, content, minrows=None, forcevalid=False):
    """
    TODO: restrict globus access to endpoint
    """
    #restrict_globus_permissions(globus_uuid)
    validate_metadata = vp.validate_metadata_for_payload(callback_id, content)
    if any([i['errorCode'] for i in json.loads(validate_metadata)['validationList']]):
        #metadata invalid stop here
        return validate_metadata

    par_dir = os.path.join(config.STORAGE_PATH, callback_id)
    payload_path = os.path.join(par_dir, "payload.json")
    nextflow_config_path = os.path.join(par_dir, "nextflow.config")
    log_dir = os.path.join(config.STORAGE_PATH, 'logs', callback_id)
    if config.VALIDATE_WITH_SSH == 'true':
        nf_script_path = os.path.join(par_dir, "validate_submission.nf")
        nextflow_cmd = nextflow_command_string(callback_id, payload_path, log_dir, par_dir, minrows, forcevalid, nextflow_config_path, nf_script_path)
        logger.debug('Validate with ssh')
        ssh = sshc.SSHClient(host=config.COMPUTE_FARM_LOGIN_NODE, username=config.COMPUTE_FARM_USERNAME)
        ssh.mkdir(par_dir)
        ssh.write_data_to_file(json.dumps(content), payload_path)
        ssh.write_data_to_file(config.NEXTFLOW_CONFIG, nextflow_config_path)
        with open("workflows/validate_submission.nf", "r") as f:
            ssh.write_data_to_file(f.read(), nf_script_path)
        ssh.write_data_to_file(json.dumps(content), payload_path)
        logger.info('content:\n{}'.format(content))
        memory = 5600
        command = cluster_command(par_dir, log_dir, memory, nextflow_cmd)
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
                    contents_list = file_contents.replace('}{', '}|{').split('|') if len(file_contents) > 0 else False
                if status in ['PEND', 'RUN']:
                    continue
                else:
                    print(status)
                    break
        if contents_list:
            contents_list_of_dicts = [json.loads(i) for i in contents_list]
            results = {
                    "callbackID": callback_id,
                    "validationList" : contents_list_of_dicts
                  }
            results = add_errors_if_study_missing(callback_id, content, results)
        else:
            results = results_if_failure(callback_id, content)
        ssh.rm(par_dir)
        ssh.close_connection()
        logger.info(results)
        return json.dumps(results)
    else:
        logger.debug('Validate without ssh')
        nextflow_cmd = nextflow_command_string(callback_id, payload_path, log_dir, par_dir, minrows, forcevalid, nextflow_config_path)
        return validate_files_NOT_SSH(callback_id, content, par_dir, payload_path, nextflow_config_path, log_dir, nextflow_cmd)

def skip_validation_completely(callback_id, content):
    results = {
        "callbackID": callback_id,
        "validationList": []
    }
    payload = pl.Payload(callback_id=callback_id, payload=content)
    payload.create_study_obj_list()
    study_list = [s.study_id for s in payload.study_obj_list]
    for study in study_list:
        results['validationList'].append({"id": study, "retrieved": 99, "dataValid": 99, "errorCode": None})
    return json.dumps(results)


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
            
    
def validate_files(callback_id, content, minrows=None, forcevalid=False):
    validate_metadata = vp.validate_metadata_for_payload(callback_id, content)
    if any([i['errorCode'] for i in json.loads(validate_metadata)['validationList']]):
        # metadata invalid stop here
        return validate_metadata
    wd, payload_path, nextflow_config_path, log_dir, nf_script_path = setup_dir_for_validation(callback_id)
    nextflow_cmd = nextflow_command_string(callback_id, payload_path, log_dir, minrows, forcevalid,
                                           nextflow_config_path, wd, nf_script_path)
    logger.info(nextflow_cmd)
    write_data_to_path(data=json.dumps(content), path=payload_path)
    write_data_to_path(data=config.NEXTFLOW_CONFIG, path=nextflow_config_path)
    with open("workflows/process_submission.nf", 'r') as f:
        write_data_to_path(data=f.read(), path=nf_script_path)
    subprocess.run(nextflow_cmd.split(),capture_output=True)
    json_out_files = glob.glob(os.path.join(wd, '[!payload]*.json'))
    results = {
                "callbackID": callback_id,
                "validationList": []
              }
    if len(json_out_files) > 0:
        for j in json_out_files:
            with open(j, 'r') as f:
                results["validationList"].append(json.load(f))
        add_errors_if_study_missing(callback_id, content, results)
    else:
        results = results_if_failure(callback_id, content)
    logger.info("results: " + json.dumps(results))
    #remove_payload_files(callback_id)
    return json.dumps(results)

def write_data_to_path(data, path):
    with open(path, "w") as f:
        f.write(data)

def setup_dir_for_validation(callback_id):
    # fast access dir
    par_dir = os.path.join(config.STORAGE_PATH, callback_id)
    # working dir
    wd = os.path.join(config.VALIDATED_PATH, callback_id)
    payload_path = os.path.join(wd, "payload.json")
    nextflow_config_path = os.path.join(wd, "nextflow.config")
    nf_script_path = os.path.join(wd, "validate_submission.nf")
    log_dir = os.path.join(wd, 'logs')
    Path(par_dir).mkdir(parents=True, exist_ok=True)
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    return wd, payload_path, nextflow_config_path, log_dir, nf_script_path


def results_if_failure(callback_id, content):
    payload = pl.Payload(callback_id=callback_id, payload=content)
    payload.create_study_obj_list()
    results = vp.construct_failure_response(callback_id, payload)
    return results


def nextflow_command_string(callback_id, payload_path, log_dir, minrows, forcevalid,
                            nextflow_config_path, wd, nf_script_path='workflows/process_submission.nf'):
    nextflow_cmd = ("nextflow -log {logs}/nextflow.log "
                    "run {script} "
                    "--payload {plp} "
                    "--storePath {sp} "
                    "--cid {cid} "
                    "--depo_data {dd} "
                    "--minrows {mr} "
                    "--forcevalid {fv} "
                    "--validatedPath {vp} "
                    "-w {wd} "
                    "-c {conf} "
                    "-with-singularity docker://{image}:{tag}").format(image=config.SINGULARITY_IMAGE,
                                                                       tag=config.SINGULARITY_TAG,
                                                                       script=nf_script_path,
                                                                       cid=callback_id,
                                                                       sp=config.STORAGE_PATH,
                                                                       vp=config.VALIDATED_PATH,
                                                                       dd=config.DEPO_PATH,
                                                                       plp=payload_path,
                                                                       logs=log_dir,
                                                                       wd=wd,
                                                                       mr=minrows,
                                                                       fv=forcevalid,
                                                                       conf=nextflow_config_path)
    return nextflow_cmd


def cluster_command(par_dir, log_dir, memory, nextflow_cmd):
    command = ("export http_proxy={hp}; "
               "export https_proxy={hsp}; "
               "export VALIDATE_WITH_SSH={ssh}; "
               "export PATH=$PATH:{sw}; "
               "mkdir -p {logs}; "
               "bsub -oo {logs}/stdout -eo {logs}/stderr "
               "-q {q} "
               "-M {mem} -R 'rusage[mem={mem}]' "
               "'{nextflow_cmd}'").format(
                    pd=par_dir,
                    q=config.COMPUTE_FARM_QUEUE_LONG,
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
        raise RequestedNotFound("Couldn't find resource with callback id: {}".format(callback_id))
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


def publish_and_clean_sumstats(study_list):
    # 1) move sumstats files to staging for publishing
    # 2) deactivate globus endpoint
    moved = 0
    callback_id = None
    globus_endpoint_id = None
    for s in study_list['studyList']:
        study = st.Study(study_id=s['id'], file_path=s['file_path'],
                        assembly=s['assembly'], callback_id=s['callback_id'],
                        readme=s['readme'], entryUUID=s['entryUUID'],
                        author_name=s['author_name'], pmid=s['pmid'],
                        gcst=s['gcst'], raw_ss=s['rawSS'], md5=s['md5'])
        if study.move_file_to_staging() is True:
            moved += 1
        if callback_id is None:
            callback_id = s['callback_id']
        if globus_endpoint_id is None:
            globus_endpoint_id = s['entryUUID']
    if callback_id and globus_endpoint_id:
        payload = pl.Payload(callback_id=callback_id)
        payload.get_data_for_callback_id()
        if len(payload.study_obj_list) == moved:
            delete_globus_endpoint(globus_endpoint_id)


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
                        "author_name": study.author_name,
                        "rawSS": study.raw_ss,
                        "md5": study.md5
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


def val_from_dict(key, dict, default=None):
    return dict[key] if key in dict else default