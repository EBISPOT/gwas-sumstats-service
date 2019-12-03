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

def create_href(method_name, params=None):
    params = params or {}
    params['_external'] = True
    return {'href': unquote(
        url_for(method_name, **params)
    )}

def json_payload_to_db(content):
    payload = pl.Payload(payload=content)
    payload.payload_to_db()
    return payload.callback_id

def store_validation_results_in_db(validation_response):
    for item in json.loads(validation_response)['validationList']:
        study_id = item["id"]
        study = st.Study(study_id)
        study.retrieved = item["retrieved"]
        study.data_valid = item["dataValid"]
        study.error_code = item["errorCode"]
        study.store_validation_statuses()

def validate_files_from_payload(callback_id, content):
    if config.VALIDATE_WITH_SSH == 'true':
        ssh = sshc.SSHClient(host=config.COMPUTE_FARM_LOGIN_NODE, username=config.COMPUTE_FARM_USERNAME)
        par_dir = os.path.join(config.STORAGE_PATH, callback_id)
        outfile = os.path.join(par_dir, 'validation.json')
        memory = 4000
        content = json.dumps(content).translate(str.maketrans({'"':  '\\"'}))
        bsub_com = 'singularity exec --bind {sp} docker://{image}:{tag} validate-payload -cid {cid} -out {outfile} -storepath {sp} -payload \'{content}\''.format(
                image=config.SINGULARITY_IMAGE, tag=config.SINGULARITY_TAG, cid=callback_id, outfile=outfile, sp=config.STORAGE_PATH, content=content)
        command = 'export http_proxy={hp}; export https_proxy={hsp}; mkdir -p {pd}; bsub -oo {pd}/stdout -eo {pd}/stderr -M {mem} -R "rusage[mem={mem}]" "{bsub_com}"'.format(
                pd=par_dir, q=config.COMPUTE_FARM_QUEUE, mem=memory, bsub_com=bsub_com, hp=config.HTTP_PROXY, hsp=config.HTTPS_PROXY)
        stdin, stdout, stderr = ssh.exec_command(command)
        jobid = ssh.parse_jobid(stdout)
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
        return vp.validate_files_from_payload(callback_id, content)
    

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



def construct_get_payload_response(callback_id):
    payload = pl.Payload(callback_id=callback_id)
    payload.get_data_for_callback_id()
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

def create_study_report(study):
    report = {
              "id": study.study_id,
              "status": study.get_status(),
              "error": study.get_error_report()
              }
    return report
