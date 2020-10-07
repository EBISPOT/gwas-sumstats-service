import json
from urllib.parse import unquote
from flask import url_for
import config
from sumstats_service.resources.error_classes import *
import sumstats_service.resources.payload as pl
import sumstats_service.resources.study_service as st
import sumstats_service.resources.validate_payload as vp
import sumstats_service.resources.ssh_client as sshc
import os
import time
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
    for item in json.loads(validation_response)['validationList']:
        study_id = item["id"]
        study = st.Study(study_id)
        study.retrieved = item["retrieved"]
        study.data_valid = item["dataValid"]
        study.error_code = item["errorCode"]
        study.store_validation_statuses()

def validate_files_from_payload(callback_id, content, minrows=None):
    if config.VALIDATE_WITH_SSH == 'true':
        logger.debug('Validate with ssh')
        ssh = sshc.SSHClient(host=config.COMPUTE_FARM_LOGIN_NODE, username=config.COMPUTE_FARM_USERNAME)
        par_dir = os.path.join(config.STORAGE_PATH, callback_id)
        outfile = os.path.join(par_dir, 'validation.json')
        memory = 16000
        ssh.mkdir(par_dir)
        payload_path = os.path.join(par_dir, "payload.json")
        ssh.write_data_to_file(json.dumps(content), payload_path)
        logger.debug('content:\n{}'.format(content))
        bsub_com = 'singularity exec --bind {sp} docker://{image}:{tag} validate-payload -cid {cid} -out {outfile} -storepath {sp} -validated_path {vp} -ftpserver {ftps} -ftpuser {ftpu} -ftppass {ftpp} -payload {plp}'.format(
                image=config.SINGULARITY_IMAGE, tag=config.SINGULARITY_TAG, cid=callback_id, outfile=outfile, sp=config.STORAGE_PATH, vp=config.VALIDATED_PATH, ftps=config.FTP_SERVER, ftpu=config.FTP_USERNAME, ftpp=config.FTP_PASSWORD, plp=payload_path)
        command = 'export http_proxy={hp}; export https_proxy={hsp}; export VALIDATE_WITH_SSH={ssh}; bsub -oo {pd}/stdout -eo {pd}/stderr -M {mem} -R "rusage[mem={mem}]" "{bsub_com}"'.format(
                pd=par_dir, q=config.COMPUTE_FARM_QUEUE, mem=memory, bsub_com=bsub_com, hp=config.REMOTE_HTTP_PROXY, hsp=config.REMOTE_HTTPS_PROXY, ssh=config.VALIDATE_WITH_SSH)
        logger.debug('command:\n{}'.format(command))
        stdin, stdout, stderr = ssh.exec_command(command)
        jobid = ssh.parse_jobid(stdout)
        logger.debug('jobid[]:\n'.format(jobid))
        results = None
        if jobid is None:
            print("command didn't return a jobid")
        else:
            while not results: 
                time.sleep(8)
                status = ssh.get_job_status(jobid)
                if status == 'DONE':
                    results = ssh.get_file_content(outfile)
                if status in ['PEND', 'RUN']:
                    continue
                if status == 'EXIT':
                    break
                    # check reason - reallocate mem
                else:
                    print(status)
                    break
        attempts = 1
        ssh.close_connection()
        if results:
            return results
        else:
            return vp.construct_failure_response
    else:
        # maintain this for the sandbox which cannot ssh ebi farm
        logger.debug('Validate without ssh')
        return vp.validate_files_from_payload(callback_id, content, minrows=minrows)
    

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
                "completed": "DELETED",
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
            completed = payload.get_payload_complete_status()
            status_list = []
            for study in payload.study_obj_list:
                study_report = create_study_report(study)
                status_list.append(study_report)
            response = {"callbackID": str(callback_id),
                        "completed": completed,
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
