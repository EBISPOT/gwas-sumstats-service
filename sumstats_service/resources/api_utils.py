import ftplib
import glob
import hashlib
import json
import logging
import os
import subprocess
import urllib
from datetime import date
from pathlib import Path
from typing import Union
from urllib.parse import unquote

from flask import url_for
from gwas_sumstats_tools.interfaces.metadata import (
    MetadataClient,
    metadata_dict_from_gwas_cat,
)
from pymongo import UpdateOne

import sumstats_service.resources.globus as globus
import sumstats_service.resources.payload as pl
import sumstats_service.resources.study_service as st
import sumstats_service.resources.validate_payload as vp
from sumstats_service import config, logger_config
from sumstats_service.resources.error_classes import RequestedNotFound
from sumstats_service.resources.mongo_client import MongoClient
from sumstats_service.resources.utils import download_with_requests

try:
    logger_config.setup_logging()
    logger = logging.getLogger(__name__)
except Exception as e:
    logging.basicConfig(level=logging.DEBUG, format="(%(levelname)s): %(message)s")
    logger = logging.getLogger(__name__)
    logger.error(f"Logging setup failed: {e}")


def create_href(method_name, params=None):
    params = params or {}
    params["_external"] = True
    return {"href": unquote(url_for(method_name, **params))}


def json_payload_to_db(content, file_type=None, callback_id=None):
    payload = pl.Payload(payload=content, file_type=file_type, callback_id=callback_id)
    payload.payload_to_db(file_type=file_type)
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
    payload.store_bypass_validation_status(bypass_validation=bypass_validation)


def store_validation_results_in_db(validation_response, is_force_valid=False):
    valid = True
    validation_list = json.loads(validation_response)["validationList"]
    callback_id = json.loads(validation_response)["callbackID"]

    bulk_operations = []

    for item in validation_list:
        study_id = item["id"]
        study = st.Study(study_id)
        study.retrieved = item["retrieved"]
        study.data_valid = item["dataValid"]
        study.error_code = item["errorCode"]
        # study.store_validation_statuses()

        update_fields = {
            "retrieved": study.retrieved,
            "dataValid": study.data_valid,
            "errorCode": study.error_code,
        }

        if is_force_valid:
            update_fields["fileType"] = determine_file_type(
                is_in_file=True, is_force_valid=True
            )

        update_operation = UpdateOne({"studyID": study_id}, {"$set": update_fields})

        bulk_operations.append(update_operation)

        if study.error_code:
            valid = False

    if bulk_operations:
        study.bulk_store_validation_statuses(bulk_operations)

    if not valid:
        """
        TODO: reinstate globus permissions
        """
        # reinstate_globus_permissions(globus_uuid)
        payload = pl.Payload(callback_id=callback_id)
        payload.remove_payload_directory()


def delete_globus_endpoint(globus_uuid):
    logger.info(f">> delete globus endpoint {globus_uuid}")
    status = globus.remove_endpoint_and_all_contents(globus_uuid)
    logger.info(f">> delete globus endpoint {globus_uuid} :: {status=}")
    return status


def skip_validation_completely(callback_id, content, file_type=None):
    results = {"callbackID": callback_id, "validationList": []}
    payload = pl.Payload(callback_id=callback_id, payload=content, file_type=file_type)
    payload.create_study_obj_list(file_type)
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
    file_type: Union[str, None] = None,
):
    print(f"[validate_files] for {callback_id=}")
    print(f"{minrows=} {forcevalid=} {file_type=}")

    validate_metadata = vp.validate_metadata_for_payload(
        callback_id, content, file_type
    )
    if any([i["errorCode"] for i in json.loads(validate_metadata)["validationList"]]):
        # metadata invalid stop here
        print("Error code exists!")
        return validate_metadata

    print("No error code.")
    (
        wd,
        payload_path,
        nextflow_config_path,
        log_dir,
        nf_script_path,
    ) = setup_dir_for_validation(callback_id)
    nextflow_cmd = nextflow_command_string(
        callback_id=callback_id,
        payload_path=payload_path,
        log_dir=log_dir,
        minrows=minrows,
        forcevalid=forcevalid,
        nextflow_config_path=nextflow_config_path,
        wd=wd,
        nf_script_path=nf_script_path,
    )
    print(nextflow_cmd)
    write_data_to_path(data=json.dumps(content), path=payload_path)
    write_data_to_path(data=config.NEXTFLOW_CONFIG, path=nextflow_config_path)
    with open(
        os.path.join(
            os.path.dirname(__file__), "../../workflows/process_submission.nf"
        ),
        "r",
    ) as f:
        write_data_to_path(data=f.read(), path=nf_script_path)

    try:
        print("Running NextFlow command...")
        result = subprocess.run(
            nextflow_cmd, capture_output=True, text=True, shell=True
        )

        if result.returncode != 0:
            print("Error in submitting job: ", result.stderr)
        else:
            print("No error. Command output: ", result.stdout)

    except Exception as e:
        print("=== EXCEPTION ===")
        print(e)

    json_out_files = [
        f
        for f in glob.glob(os.path.join(wd, "*.json"))
        if not f.endswith("payload.json")
    ]
    results = {"callbackID": callback_id, "validationList": []}
    if len(json_out_files) > 0:
        for j in json_out_files:
            with open(j, "r") as f:
                results["validationList"].append(json.load(f))
        add_errors_if_study_missing(callback_id, content, results)
    else:
        results = results_if_failure(callback_id, content)

    results_json_dumped = json.dumps(results)
    print("results: " + results_json_dumped)
    # remove_payload_files(callback_id)
    return results_json_dumped


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
        f"--validatedPath {config.VALIDATED_PATH} "
        f"-w {wd} "
        f"-c {nextflow_config_path} "
        f"-with-singularity {config.SINGULARITY_IMAGE}_{config.SINGULARITY_TAG}.sif"
    )
    if containerise == "False":
        nextflow_cmd = nextflow_cmd.split("-with-singularity")[0]
    return nextflow_cmd


def validate_metadata(callback_id):
    metadata_valid = []
    payload = pl.Payload(callback_id=callback_id)
    payload.get_data_for_callback_id()
    for study in payload.study_obj_list:
        metadata_valid.append(
            study.validate_metadata()  # pytype: disable=attribute-error
        )
    if not any(metadata_valid):
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


def move_files_to_staging(study_list):
    logger.info(f"==> Move sumstats files to staging for publishing for {study_list=}")

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

        if study.move_file_to_staging():
            moved += 1

        if callback_id is None:
            callback_id = s["callback_id"]

        if globus_endpoint_id is None:
            globus_endpoint_id = s["entryUUID"]

    return {
        "moved": moved,
        "callback_id": callback_id,
        "globus_endpoint_id": globus_endpoint_id,
    }


def determine_file_type(is_in_file, is_force_valid) -> str:
    return (
        "Non-GWAS-SSF"
        if is_force_valid
        else config.SUMSTATS_FILE_TYPE + ("-incomplete-meta" if not is_in_file else "")
    )


def get_template(callback_id):
    """
    Get template or None
    download template
    :param self:
    :return: bytes or None
    """
    return download_with_requests(
        url=urllib.parse.urljoin(config.GWAS_DEPO_REST_API_URL, "submissions/uploads"),
        params={"callbackId": callback_id},
        headers={"jwt": config.DEPO_API_AUTH_TOKEN},
    )


def get_file_type_from_mongo(gcst) -> str:
    try:
        logger.debug(f"Fetching the `file_type` for {gcst=}")
        mdb = MongoClient(
            config.MONGO_URI,
            config.MONGO_USER,
            config.MONGO_PASSWORD,
            config.MONGO_DB,
        )
        study_metadata = mdb.get_study_metadata_by_gcst(gcst)
        return study_metadata["fileType"]
    except Exception as e:
        logger.error(f"Error while fetching the `file_type`: {e=}")
        return ""


def save_convert_metadata_to_yaml(
    gcst_id: str, is_harmonised_included: bool, globus_endpoint_id: str
):
    logger.info(
        f"""save_convert_metadata_to_yaml called for {gcst_id}
        and hm: {is_harmonised_included}"""
    )

    mdb = MongoClient(
        config.MONGO_URI,
        config.MONGO_USER,
        config.MONGO_PASSWORD,
        config.MONGO_DB,
    )
    study_data = mdb.get_study(gcst_id=gcst_id)
    if not study_data or study_data.get("summaryStatisticsFile", "") != config.NR:
        logger.info(f"Adding {gcst_id=} to the metadata yaml collection")
        mdb.insert_or_update_metadata_yaml_request(
            gcst_id=gcst_id,
            status=config.MetadataYamlStatus.PENDING,
            globus_endpoint_id=globus_endpoint_id,
        )

        if is_harmonised_included:
            logger.info(
                f"""Adding {gcst_id=} hm:{is_harmonised_included}
                to the metadata yaml collection"""
            )
            mdb.insert_or_update_metadata_yaml_request(
                gcst_id=gcst_id,
                status=config.MetadataYamlStatus.PENDING,
                is_harmonised=True,
            )
    else:
        logger.info(
            f"Adding {gcst_id=} to the metadata yaml coll as it has no sumstats."
        )
        additional_info = {"note": f"GCST ID {gcst_id} do not have summary statistics."}
        mdb.insert_or_update_metadata_yaml_request(
            gcst_id=gcst_id,
            status=config.MetadataYamlStatus.COMPLETED,
            additional_info=additional_info,
        )

        if is_harmonised_included:
            mdb.insert_or_update_metadata_yaml_request(
                gcst_id=gcst_id,
                status=config.MetadataYamlStatus.COMPLETED,
                is_harmonised=True,
            )

    return True


def generate_yaml_hm(accession_id, is_harmonised_included):
    logger.info(f"HM CASE for {accession_id=}")
    logger.info(
        f"For HM {accession_id=} - resetting data_file_name and data_file_md5sum"
    )

    # Consume Ingest API via gwas-sumstats-tools
    metadata_from_gwas_cat = metadata_dict_from_gwas_cat(
        accession_id=accession_id,
        is_bypass_rest_api=True,
        # DEV ONLY #######
        # 1. Update for Sandbox in gwas-sumstats-tools
        # 2. Make a pre-release
        #
    )
    logger.info(f"For hm {accession_id=} - {metadata_from_gwas_cat=}")
    metadata_from_gwas_cat["date_metadata_last_modified"] = date.today()
    metadata_from_gwas_cat["file_type"] = get_file_type_from_mongo(accession_id)

    metadata_from_gwas_cat["data_file_name"] = ""
    metadata_from_gwas_cat["data_file_md5sum"] = ""
    metadata_from_gwas_cat["harmonisation_reference"] = config.HM_REFERENCE
    metadata_from_gwas_cat["coordinate_system"] = config.HM_COORDINATE_SYSTEM
    metadata_from_gwas_cat["genome_assembly"] = config.LATEST_ASSEMBLY
    metadata_from_gwas_cat["is_harmonised"] = True
    metadata_from_gwas_cat["is_sorted"] = get_is_sorted(
        config.FTP_SERVER_EBI,
        f"{config.FTP_PREFIX}/{generate_path(accession_id)}/{accession_id}/harmonised",
    )
    metadata_from_gwas_cat["gwas_id"] = accession_id
    metadata_from_gwas_cat["gwas_catalog_api"] = (
        f"{config.GWAS_CATALOG_REST_API_STUDY_URL}{accession_id}"
    )

    # We don't use staging ftp because old harmonised files are not in there
    # but only in public ftp
    filenames_to_md5_values = compute_md5_for_ftp_files(
        config.FTP_SERVER_EBI,
        f"{config.FTP_PREFIX}/{generate_path(accession_id)}/{accession_id}/harmonised",
        accession_id,
    )
    filename_to_md5sum_hm = get_md5_for_accession(
        filenames_to_md5_values,
        accession_id,
        True,
    )
    for k, v in filename_to_md5sum_hm.items():
        metadata_from_gwas_cat["data_file_name"] = k
        metadata_from_gwas_cat["data_file_md5sum"] = v

    if not metadata_from_gwas_cat.get("data_file_name"):
        logger.info(
            f"""
            HM data file not available for {accession_id} at
            '{config.FTP_PREFIX}/{generate_path(accession_id)}/{accession_id}/harmonised'
            """
        )
        raise FileNotFoundError(
            f"""
            HM data file not available for {accession_id} at
            '{config.FTP_PREFIX}/{generate_path(accession_id)}/{accession_id}/harmonised'
            """
        )

    out_dir = os.path.join(config.STAGING_PATH, accession_id)
    hm_dir = os.path.join(out_dir, "harmonised")
    Path(hm_dir).mkdir(parents=True, exist_ok=True)

    metadata_filename_hm = f"{metadata_from_gwas_cat['data_file_name']}-meta.yaml"
    out_file_hm = os.path.join(hm_dir, metadata_filename_hm)
    logger.info(f"For HM {accession_id=} - {out_file_hm=}")

    # Also generate client for hm case, i.e., if is_harmonised_included
    metadata_client_hm = MetadataClient(out_file=out_file_hm)

    logger.info(f"For HM {accession_id=} updated -> {metadata_from_gwas_cat=}")
    metadata_client_hm.update_metadata(metadata_from_gwas_cat)

    metadata_client_hm.to_file()

    filenames_to_md5_values[metadata_filename_hm] = compute_md5_local(out_file_hm)
    logger.info(f"For HM {accession_id=} - {filenames_to_md5_values=}")

    write_md5_for_files(filenames_to_md5_values, os.path.join(hm_dir, "md5sum.txt"))
    logger.info(f"Metadata yaml file creation is successful for HM {accession_id=}.")

    logger.info(f"::: ENDOF [convert_metadata_to_yaml] for {accession_id=}:::")

    return True


def generate_yaml_non_hm(accession_id, is_harmonised_included):
    logger.info(f"Non-HM case for {accession_id=}")

    # Consume Ingest API via gwas-sumstats-tools
    metadata_from_gwas_cat = metadata_dict_from_gwas_cat(
        accession_id=accession_id,
        is_bypass_rest_api=True,
        # DEV ONLY #######
        # 1. Update for Sandbox in gwas-sumstats-tools
        # 2. Make a pre-release
        #
    )
    logger.info(f"For non-hm {accession_id=} - {metadata_from_gwas_cat=}")
    metadata_from_gwas_cat["date_metadata_last_modified"] = date.today()
    metadata_from_gwas_cat["file_type"] = get_file_type_from_mongo(accession_id)

    metadata_from_gwas_cat["is_harmonised"] = False
    metadata_from_gwas_cat["is_sorted"] = False
    metadata_from_gwas_cat["harmonisation_reference"] = None

    # Setting default values for keys that may not exist
    default_keys = [
        "genome_assembly",
        "data_file_name",
        "file_type",
        "data_file_md5sum",
    ]
    for key in default_keys:
        logger.info(f"For non-hm {accession_id=} - Setting default value for {key=}.")
        metadata_from_gwas_cat.setdefault(key, "")

    logger.info(f"{accession_id=}")
    filenames_to_md5_values = compute_md5_for_local_files(
        accession_id=accession_id,
        path=os.path.join(
            config.FTP_STAGING_PATH, generate_path(accession_id), accession_id
        ),
    )

    filename_to_md5sum = get_md5_for_accession(
        filenames_to_md5_values,
        accession_id,
    )
    # set if exists, default value set above
    for k, v in filename_to_md5sum.items():
        metadata_from_gwas_cat["data_file_name"] = k
        metadata_from_gwas_cat["data_file_md5sum"] = v

    if not metadata_from_gwas_cat.get("data_file_name"):
        logger.info("Data file not available in FTP")
        raise FileNotFoundError(
            f"""
            Data file not available for {accession_id}
            at '{config.FTP_STAGING_PATH}/{generate_path(accession_id)}/{accession_id}'
            """
        )

    metadata_from_gwas_cat["gwas_id"] = accession_id
    metadata_from_gwas_cat["gwas_catalog_api"] = (
        f"{config.GWAS_CATALOG_REST_API_STUDY_URL}{accession_id}"
    )

    # Create out_dir as late as possible to make sure that it's not empty
    out_dir = os.path.join(config.STAGING_PATH, accession_id)
    logger.info(f"For non-hm {accession_id=} - {out_dir=}")
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    metadata_filename = f"{metadata_from_gwas_cat['data_file_name']}-meta.yaml"
    out_file = os.path.join(out_dir, metadata_filename)
    logger.info(f"For non-hm {accession_id=} - {out_file=}")
    metadata_client = MetadataClient(out_file=out_file)

    logger.info(f"For non-hm {accession_id=} updated -> {metadata_from_gwas_cat=}")
    metadata_client.update_metadata(metadata_from_gwas_cat)

    metadata_client.to_file()

    # compute md5sum of the meta file and write to md5sum.txt here
    filenames_to_md5_values[metadata_filename] = compute_md5_local(out_file)
    logger.info(f"For non-hm {accession_id=} - {filenames_to_md5_values=}")

    write_md5_for_files(filenames_to_md5_values, os.path.join(out_dir, "md5sum.txt"))

    logger.info(
        f"Metadata yaml file creation is successful for non-hm {accession_id=}."
    )

    if not is_harmonised_included:
        return True


def convert_metadata_to_yaml(accession_id: str, is_harmonised_included: bool):
    logger.info(f"::: [convert_metadata_to_yaml] {accession_id=} :::")
    try:
        if not is_harmonised_included:
            generate_yaml_non_hm(accession_id, is_harmonised_included)
        else:
            generate_yaml_hm(accession_id, is_harmonised_included)

        mdb = MongoClient(
            config.MONGO_URI,
            config.MONGO_USER,
            config.MONGO_PASSWORD,
            config.MONGO_DB,
        )
        mdb.insert_or_update_metadata_yaml_request(
            gcst_id=accession_id,
            status=config.MetadataYamlStatus.COMPLETED,
            is_harmonised=is_harmonised_included,
        )
    except Exception:
        logger.error(
            f"Error generating yaml for {accession_id} - hm: {is_harmonised_included}"
        )
        raise


def generate_path(gcst_id):
    if not gcst_id.startswith("GCST"):
        raise ValueError("Invalid GCST ID format.")

    # Note that -1 required for edge cases,
    # e.g., 'GCST90427001-GCST90428000/GCST90428000'
    num_part = int(gcst_id[4:]) - 1

    lower_bound = (num_part // 1000) * 1000 + 1
    upper_bound = lower_bound + 999
    num_digits = len(gcst_id) - 4

    # Do zero-padding accordingly
    return f"GCST{lower_bound:0{num_digits}d}-GCST{upper_bound:0{num_digits}d}"


def get_is_sorted(ftp_server: str, ftp_directory: str):
    try:
        with ftplib.FTP(ftp_server) as ftp:
            ftp.login()
            ftp.cwd(ftp_directory)
            return any(f.endswith(".tbi") for f in ftp.nlst())
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False


def compute_md5_for_ftp_files(ftp_server: str, ftp_directory: str, file_id: str):
    """Compute MD5 checksums for files in an FTP directory."""
    filename_to_md5 = {}

    try:
        with ftplib.FTP(ftp_server) as ftp:
            try:
                ftp.login()
                ftp.cwd(ftp_directory)
                files = ftp.nlst()
            except ftplib.error_perm as e:
                logger.error(f"FTP error: {e}")
                return {}

            # Filter out hidden files
            files_of_interest = [f for f in files if not f.startswith(".")]

            for filename in files_of_interest:
                try:
                    md5_checksum = compute_md5_ftp(ftp, ftp_directory, filename)
                    filename_to_md5[filename] = md5_checksum
                except Exception as e:
                    logger.error(f"Error computing MD5 for {filename}: {e}")
                    continue

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {}

    return filename_to_md5


def write_md5_for_files(filename_to_md5: dict, output_file: str) -> None:
    with open(output_file, "w") as f:
        for filename, md5_checksum in filename_to_md5.items():
            f.write(f"{md5_checksum} {filename}\n")


def compute_md5_for_local_files(accession_id, path):
    """
    Compute MD5 checksums for files starting with a specific ID in codon dir and
    write to a file.
    """
    md5_lines = []
    filename_to_md5 = {}
    logger.info(f"Compute md5sum for files in {path=}")

    if not os.path.exists(path):
        raise FileNotFoundError(f"The directory {path} does not exist.")

    # List files in the directory, excluding hidden files
    files_of_interest = [
        f
        for f in os.listdir(path)
        if os.path.isfile(os.path.join(path, f)) and not f.startswith(".")
    ]
    logger.info(f"{files_of_interest=}")

    # Compute MD5 for each file and store the line for the output file
    for filename in files_of_interest:
        file_path = os.path.join(path, filename)
        md5_checksum = compute_md5_local(file_path)
        md5_lines.append(f"{md5_checksum} {filename}")
        filename_to_md5[filename] = md5_checksum

    logger.info(f"{filename_to_md5=}")

    return filename_to_md5


def compute_md5_local(file_path: str) -> str:
    """Compute the MD5 checksum of a file."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def compute_md5_ftp(ftp: ftplib.FTP, ftp_path: str, filename: str) -> str:
    """Compute MD5 checksum for a single file on an FTP server using an existing
    FTP connection."""
    md5 = hashlib.md5()

    def handle_binary(m):
        md5.update(m)

    ftp.retrbinary(f"RETR {filename}", handle_binary)

    return md5.hexdigest()


def get_md5_for_accession(
    md5_checksums: dict,
    accession_id: str,
    is_harmonised=False,
) -> dict:
    """
    Return the key (filename) and value (MD5 checksum) from md5_checksums.

    First, check if there's a key that ends with accession_id.tsv.gz or
    accession_id.tsv OR accession_id.h.tsv.gz or accession_id.h.tsv.

    Then check for partial matches if no exact match is found.

    If still no match, look for any .tsv, .tsv.gz, .txt or .txt.gz files.

    Parameters:
    - md5_checksums: Dictionary with filenames as keys and their MD5 checksums as
    values.
    - accession_id: The accession ID to look for, with .tsv or .tsv.gz extensions.
    - is_harmonised: Boolean to look for files in harmonised folders

    Returns:
    - A dictionary with the matching filename and its MD5 checksum. Empty if no
    match is found.
    """
    # Check for exact matches first
    for key in md5_checksums:
        if not is_harmonised:
            if key.endswith((f"{accession_id}.tsv", f"{accession_id}.tsv.gz")):
                return {key: md5_checksums[key]}
        else:
            if key.endswith((f"{accession_id}.h.tsv", f"{accession_id}.h.tsv.gz")):
                return {key: md5_checksums[key]}

    # Check for partial matches if no exact match is found
    # i.e., files are named <GCST ID>_<build number>.*
    # e.g. http://ftp.ebi.ac.uk/pub/databases/gwas/summary_statistics/GCST90308001-GCST90309000/GCST90308682/ # noqa:E501
    for key in md5_checksums:
        if (
            accession_id in key
            and key.endswith((".tsv", ".tsv.gz", ".txt", ".txt.gz", ".csv", ".csv.gz"))
            and ".yaml" not in key
            and ".tbi" not in key
            and "running.log" not in key
            and "README" not in key
            and not key.endswith((".f.tsv", ".f.tsv.gz"))
        ):
            return {key: md5_checksums[key]}

    # If still no match, look for any .tsv, .tsv.gz, .txt or .txt.gz files
    # except md5sums.txt and YAML files. This is probably very early
    # submission where files are named freely,
    # e.g., http://ftp.ebi.ac.uk/pub/databases/gwas/summary_statistics/GCST005001-GCST006000/GCST005529/ # noqa:E501
    for key in md5_checksums:
        if (
            key.endswith((".tsv", ".tsv.gz", ".txt", ".txt.gz", ".csv", ".csv.gz"))
            and key != "md5sums.txt"
            and ".yaml" not in key
            and ".tbi" not in key
            and "running.log" not in key
            and "README" not in key
            and not key.endswith((".f.tsv", ".f.tsv.gz"))
        ):
            return {key: md5_checksums[key]}

    return {}


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
