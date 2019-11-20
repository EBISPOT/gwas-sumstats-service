import json
from urllib.parse import unquote
from flask import url_for
import config
from sumstats_service.resources.error_classes import *
import sumstats_service.resources.payload as pl
import sumstats_service.resources.study_service as st
import sumstats_service.resources.validate_payload as vp


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
    return vp.validate_files_from_payload(callback_id, content)
    # result = None
    # attempts = 1
    # ssh.submit(validate_with_singularity, cid, content)
    # ssh.poll_for_status(jobid)
    # if DONE:
    #     result = ssh.get_result(callback_id)
    # elif PEND or RUN:
    #     ssh.poll_for_status(jobid)
    # else:
    #     
    #     ssh.resubmit() # while loop everything until attempts == 2?
    #     attempts += 1



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
