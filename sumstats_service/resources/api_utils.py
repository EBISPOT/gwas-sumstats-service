import glob
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Union
from urllib.parse import unquote

from flask import url_for

import sumstats_service.resources.globus as globus
import sumstats_service.resources.payload as pl
import sumstats_service.resources.study_service as st
import sumstats_service.resources.validate_payload as vp
from sumstats_service import config
from sumstats_service.resources.error_classes import *

logging.basicConfig(level=logging.DEBUG, format="(%(levelname)s): %(message)s")
logger = logging.getLogger(__name__)


def create_href(method_name, params=None):
    params = params or {}
    params["_external"] = True
    return {"href": unquote(url_for(method_name, **params))}


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


def store_validation_method(callback_id: str, bypass_validation: bool = False) -> None:
    """Store whether the validaiton was bypassed or not

    Keyword Arguments:
        bypass_validation -- bypass status (default: {False})
    """
    payload = pl.Payload(callback_id=callback_id)
    payload.store_validation_method(bypass_validation=bypass_validation)


def store_validation_results_in_db(validation_response):
    valid = True
    for item in json.loads(validation_response)["validationList"]:
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
        # reinstate_globus_permissions(globus_uuid)
        callback_id = json.loads(validation_response)["callbackID"]
        payload = pl.Payload(callback_id=callback_id)
        payload.remove_payload_directory()


def delete_globus_endpoint(globus_uuid):
    status = globus.remove_endpoint_and_all_contents(globus_uuid)
    return status


def skip_validation_completely(callback_id, content):
    results = {"callbackID": callback_id, "validationList": []}
    payload = pl.Payload(callback_id=callback_id, payload=content)
    payload.create_study_obj_list()
    study_list = [s.study_id for s in payload.study_obj_list]
    for study in study_list:
        results["validationList"].append(
            {"id": study, "retrieved": 99, "dataValid": 99, "errorCode": None}
        )
    return json.dumps(results)


def add_errors_if_study_missing(callback_id, content, results):
    if any([s["errorCode"] for s in results["validationList"]]):
        # if we already identfied errors, there's no need to add them
        return results
    else:
        payload = pl.Payload(callback_id=callback_id, payload=content)
        payload.create_study_obj_list()
        study_list = [s.study_id for s in payload.study_obj_list]
        studies_with_results = [s["id"] for s in results["validationList"]]
        for study in study_list:
            if study not in studies_with_results:
                results["validationList"].append(
                    {"id": study, "retrieved": None, "dataValid": None, "errorCode": 10}
                )
        return results


def reset_validation_status(callback_id: str) -> None:
    """Reset the validation status for a submission

    Arguments:
        callback_id -- callback id
    """
    payload = pl.Payload(callback_id=callback_id)
    payload.reset_validation_status()


def validate_files(
    callback_id: str,
    content: dict,
    minrows: Union[int, None] = None,
    forcevalid: bool = False,
    zero_p_values: bool = False,
):
    validate_metadata = vp.validate_metadata_for_payload(callback_id, content)
    if any([i["errorCode"] for i in json.loads(validate_metadata)["validationList"]]):
        # metadata invalid stop here
        return validate_metadata
    (
        wd,
        payload_path,
        nextflow_config_path,
        log_dir,
        nf_script_path,
    ) = setup_dir_for_validation(callback_id)
    nextflow_cmd = nextflow_command_string(
        callback_id,
        payload_path,
        log_dir,
        minrows,
        forcevalid,
        zero_p_values,
        nextflow_config_path,
        wd,
        nf_script_path,
    )
    logger.info(nextflow_cmd)
    write_data_to_path(data=json.dumps(content), path=payload_path)
    write_data_to_path(data=config.NEXTFLOW_CONFIG, path=nextflow_config_path)
    with open(
        os.path.join(
            os.path.dirname(__file__), "../../workflows/process_submission.nf"
        ),
        "r",
    ) as f:
        write_data_to_path(data=f.read(), path=nf_script_path)
    subprocess.run(nextflow_cmd.split(), capture_output=True)
    json_out_files = glob.glob(os.path.join(wd, "[!payload]*.json"))
    results = {"callbackID": callback_id, "validationList": []}
    if len(json_out_files) > 0:
        for j in json_out_files:
            with open(j, "r") as f:
                results["validationList"].append(json.load(f))
        add_errors_if_study_missing(callback_id, content, results)
    else:
        results = results_if_failure(callback_id, content)
    logger.info("results: " + json.dumps(results))
    # remove_payload_files(callback_id)
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
    log_dir = os.path.join(wd, "logs")
    Path(par_dir).mkdir(parents=True, exist_ok=True)
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    return wd, payload_path, nextflow_config_path, log_dir, nf_script_path


def results_if_failure(callback_id, content):
    payload = pl.Payload(callback_id=callback_id, payload=content)
    payload.create_study_obj_list()
    results = vp.construct_failure_response(callback_id, payload)
    return results


def nextflow_command_string(
    callback_id,
    payload_path,
    log_dir,
    minrows,
    forcevalid,
    nextflow_config_path,
    wd,
    nf_script_path="workflows/process_submission.nf",
    zero_p_values=False,
    containerise=config.CONTAINERISE,
) -> str:
    """Constructor for nextflow command string"""
    nextflow_cmd = (
        f"nextflow -log {log_dir}/nextflow.log "
        f"run {nf_script_path} "
        f"--payload {payload_path} "
        f"--storePath {config.STORAGE_PATH} "
        f"--cid {callback_id} "
        f"--depo_data {config.DEPO_PATH} "
        f"--minrows {minrows} "
        f"--forcevalid {forcevalid} "
        f"--zerop {zero_p_values} "
        f"--validatedPath {config.VALIDATED_PATH} "
        f"-w {wd} "
        f"-c {nextflow_config_path} "
        f"-with-singularity $SINGULARITY_CACHEDIR/{config.SINGULARITY_IMAGE}_{config.SINGULARITY_TAG}.sif"
    )
    if containerise is False:
        nextflow_cmd = nextflow_cmd.split("-with-singularity")[0]
    return nextflow_cmd


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
        raise RequestedNotFound(
            "Couldn't find resource with callback id: {}".format(callback_id)
        )
    payload.get_data_for_callback_id()
    payload.remove_callback_id()
    status_list = []
    for study in payload.study_obj_list:
        status_list.append({"id": study.study_id, "status": "DELETED"})
        study.remove()
    response = {
        "callbackID": str(callback_id),
        "status": "DELETED",
        "statusList": status_list,
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
    for s in study_list["studyList"]:
        study = st.Study(
            study_id=s["id"],
            file_path=s["file_path"],
            assembly=s["assembly"],
            callback_id=s["callback_id"],
            readme=s["readme"],
            entryUUID=s["entryUUID"],
            author_name=s["author_name"],
            pmid=s["pmid"],
            gcst=s["gcst"],
            raw_ss=s["rawSS"],
            md5=s["md5"],
        )
        if study.move_file_to_staging() is True:
            moved += 1
        if callback_id is None:
            callback_id = s["callback_id"]
        if globus_endpoint_id is None:
            globus_endpoint_id = s["entryUUID"]
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
            response = {"callbackID": str(callback_id), "status": "PROCESSING"}
            if payload.metadata_errors:
                response["metadataErrors"] = payload.metadata_errors
                response["status"] = "INVALID"
        else:
            payload_status = payload.get_payload_status()
            status_list = []
            for study in payload.study_obj_list:
                study_report = create_study_report(study)
                status_list.append(study_report)
            response = {
                "callbackID": str(callback_id),
                "status": payload_status,
                "statusList": status_list,
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
            "md5": study.md5,
        }
        study_list.append(study_report)
    response = {"callbackID": str(callback_id), "studyList": study_list}
    return response


def create_study_report(study):
    report = {
        "id": study.study_id,
        "status": study.get_status(),
        "error": study.get_error_report(),
        "gcst": study.get_gcst(),
    }
    return report


def val_from_dict(key, dict, default=None):
    return dict[key] if key in dict else default
