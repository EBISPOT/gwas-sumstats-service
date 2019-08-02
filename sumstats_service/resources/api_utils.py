from urllib.parse import unquote
from flask import url_for
from sumstats_service.resources.error_classes import *
import sumstats_service.resources.payload as pl


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

def validate_files_from_payload(callback_id):
    payload = pl.Payload(callback_id=callback_id)
    payload.validate_payload()

def construct_get_payload_response(callback_id):
    payload = pl.Payload(callback_id=callback_id)
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
