import json
import logging
import os
import time
from typing import Union

import simplejson
from celery import Celery
from celery.signals import task_failure
from flask import Flask, Response, abort, jsonify, make_response, request

import sumstats_service.resources.api_endpoints as endpoints
import sumstats_service.resources.api_utils as au
import sumstats_service.resources.globus as globus
from sumstats_service import config, logger_config
from sumstats_service.resources.error_classes import APIException
from sumstats_service.resources.mongo_client import MongoClient
from sumstats_service.resources.utils import send_mail

try:
    logger_config.setup_logging()
    logger = logging.getLogger(__name__)
except Exception as e:
    logging.basicConfig(level=logging.DEBUG, format="(%(levelname)s): %(message)s")
    logger = logging.getLogger(__name__)
    logger.error(f"Logging setup failed: {e}")


app = Flask(__name__)
app.config["CELERY_BROKER_URL"] = "{msg_protocol}://{user}:{pwd}@{host}:{port}".format(
    msg_protocol=os.environ["CELERY_PROTOCOL"],
    user=os.environ["CELERY_USER"],
    pwd=os.environ["CELERY_PASSWORD"],
    host=os.environ["QUEUE_HOST"],
    port=os.environ["QUEUE_PORT"],
)
app.config["CELERY_RESULT_BACKEND"] = (
    "rpc://"
    # '{0}://guest@{1}:{2}'.format(config.BROKER,config.BROKER_HOST,config.BROKER_PORT)
)
app.config["BROKER_TRANSPORT_OPTIONS"] = {"confirm_publish": True}
app.url_map.strict_slashes = False


celery = Celery(
    "app",
    broker=app.config["CELERY_BROKER_URL"],
    backend=app.config["CELERY_RESULT_BACKEND"],
)
celery.conf.update(app.config)

# --- Errors --- #


@app.errorhandler(APIException)
def handle_custom_api_exception(error):
    response = error.to_dict()
    response["status"] = error.status_code
    response = simplejson.dumps(response)
    resp = make_response(response, error.status_code)
    resp.mimetype = "application/json"
    return resp


@app.errorhandler(400)
def bad_request(error):
    return make_response(jsonify({"error": "Bad request"}), 400)


@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({"error": "Not found"}), 404)


@app.errorhandler(500)
def internal_server_error(error):
    return make_response(
        jsonify(
            {
                "message": "Internal Server Error.",
                "status": 500,
                "error": "Internal Server Error",
            }
        ),
        500,
    )


# --- Sumstats service --- #


@app.route("/")
def root():
    resp = endpoints.root()
    return Response(response=resp, status=200, mimetype="application/json")


@app.route("/v1/sum-stats", methods=["POST"])
def sumstats():
    """Register sumstats and validate them"""
    content = request.get_json(force=True)

    logger.info("POST content: " + str(content))

    resp = endpoints.generate_callback_id()
    resp_dict = json.loads(resp)
    callback_id = au.val_from_dict(key="callbackID", dict=resp_dict)

    # option to force submission to be valid and continue the pipeline
    force_valid = au.val_from_dict(key="forceValid", dict=content, default=False)

    # minrows is the minimum number of rows for the validation to pass
    minrows = None if force_valid else au.val_from_dict(key="minrows", dict=content)

    # option to bypass all validation and downstream steps
    bypass = au.val_from_dict(key="skipValidation", dict=content, default=False)

    file_type = au.determine_file_type(
        is_in_file=True,
        is_force_valid=bool(force_valid),
    )

    logger.info(f"{minrows=} {force_valid=} {bypass=} {file_type=}")

    mdb = MongoClient(
        config.MONGO_URI,
        config.MONGO_USER,
        config.MONGO_PASSWORD,
        config.MONGO_DB,
    )

    mdb.upsert_payload(
        callback_id=callback_id,
        payload=content,
        status=config.ValidationStatus.PENDING,
    )

    process_studies.apply_async(
        kwargs={
            "callback_id": callback_id,
            "file_type": file_type,
            "minrows": minrows,
            "forcevalid": force_valid,
            "bypass": bypass,
        },
        retry=True,
    )
    return Response(response=resp, status=201, mimetype="application/json")


@app.route("/v1/sum-stats/validate/<string:callback_id>", methods=["POST"])
def validate_sumstats(callback_id: str):
    """Validate existing sumstats

    Arguments:
        callback_id -- callback id
    """
    body = request.get_json(force=True)
    # minrows is the minimum number of rows for the validation to pass
    minrows = au.val_from_dict(key="minrows", dict=body)
    # option to force submission to be valid and continue the pipeline
    force_valid = au.val_from_dict(key="forceValid", dict=body, default=False)
    minrows = None if force_valid is True else minrows
    content = endpoints.get_content(callback_id)
    # reset validation status
    au.reset_validation_status(callback_id=callback_id)
    # run validation

    # option to bypass all validation and downstream steps
    bypass = au.val_from_dict(key="skipValidation", dict=body, default=False)

    # determine file_type
    template = au.get_template(callback_id)
    file_type = au.determine_file_type(
        is_in_file=bool(template),
        is_force_valid=bool(force_valid),
    )

    mdb = MongoClient(
        config.MONGO_URI,
        config.MONGO_USER,
        config.MONGO_PASSWORD,
        config.MONGO_DB,
    )

    mdb.upsert_payload(
        callback_id=callback_id,
        payload=content,
        status=config.ValidationStatus.PENDING,
    )

    validate_files_in_background.apply_async(
        kwargs={
            "callback_id": callback_id,
            "minrows": minrows,
            "forcevalid": force_valid,
            "bypass": bypass,
            "file_type": file_type,
        },
        link=store_validation_results.s(force_valid),
        retry=True,
    )
    return Response(status=200, mimetype="application/json")


@app.route("/v1/sum-stats/<string:callback_id>", methods=["GET"])
def get_sumstats(callback_id):
    resp = endpoints.get_sumstats(callback_id=callback_id)
    return Response(response=resp, status=200, mimetype="application/json")


@app.route("/v1/sum-stats/<string:callback_id>", methods=["DELETE"])
def delete_sumstats(callback_id):
    resp = endpoints.delete_sumstats(callback_id=callback_id)
    if resp:
        remove_payload_files.apply_async(args=[callback_id], retry=True)
    return Response(response=resp, status=200, mimetype="application/json")


@app.route("/v1/sum-stats/<string:callback_id>", methods=["PUT"])
def update_sumstats(callback_id):
    content = request.get_json(force=True)

    resp = endpoints.update_sumstats(callback_id=callback_id, content=content)
    logger.info(f"PUT /v1/sum-stats/{callback_id}")
    logger.info(f">> {resp=}")

    if resp:
        try:
            move_files_result = move_files_to_staging.apply_async(
                args=[resp],
                retry=True,
            )
            # Wait with a timeout to avoid indefinite hanging
            timeout = 600
            start_time = time.time()

            while (time.time() - start_time) < timeout:
                if move_files_result.ready():
                    logger.info("Task move_files_result ready.")
                    break
                logger.info("Waiting for move_files_result task to complete.")
                logger.info(f"Current state: {move_files_result.state}")
                time.sleep(10)
            else:
                raise Exception(
                    "Task move_files_result did not complete within the expected time."
                )

            if move_files_result.successful():
                logger.info(f"{callback_id=} :: move_files_result successful")
                globus_endpoint_id = move_files_result.get()["globus_endpoint_id"]
                for study in resp["studyList"]:
                    metadata_conversion_result = convert_metadata_to_yaml.apply_async(
                        args=[study["gcst"]],
                        kwargs={
                            "is_harmonised_included": False,
                            "globus_endpoint_id": globus_endpoint_id,
                        },
                        retry=True,
                    )

                while (time.time() - start_time) < timeout:
                    if metadata_conversion_result.ready():
                        logger.info("Task metadata_conversion_result ready.")
                        break
                    logger.info(
                        "Waiting for metadata_conversion_result task to complete."
                    )
                    logger.info(f"Current state: {metadata_conversion_result.state}")
                    time.sleep(10)
                else:
                    raise Exception(
                        "Task metadata_conversion_result did not complete in time."
                    )
            else:
                raise Exception("Task move_files_result did not complete in time.")
        except Exception as e:
            logger.error(f"{callback_id=} :: Error {e=}")
            return Response(status=500, mimetype="application/json")

    logger.info(f"{callback_id=} :: Return status 200")
    return Response(status=200, mimetype="application/json")


@app.route("/v1/file-type", methods=["PATCH"])
def update_file_types_route():
    """
    usage:
    curl -X PATCH "gwas-ss-service-dev:8000/v1/file-type" -H "Content-Type: application/json" -d '{"gcst_id": ["GCSTXXXXXX", ...], "file_type": "<valid file type>"}'
    
    New body of request:
    {
        "gcst_id": ["GCSTXXXXXX", ...],
        "file_type": "GWAS_SUMMARY_STATISTICS"
    }

    Update the file type for a given gcst_id.
    """
    # 1. Parse JSON body
    try:
        data = request.get_json()
        if not data:
            return make_response(jsonify({"error": "Request body must be JSON"}), 400)
    except Exception as e:
        logger.error(f"Error parsing JSON: {e}")
        return make_response(jsonify({"error": "Invalid JSON format"}), 400)

    # 2. Extract gcst_id and file_type
    raw_gcst_ids = data.get("gcst_id")   # may be str or list
    file_type = data.get("file_type") # String

    if raw_gcst_ids is None:
        return make_response(jsonify({"error": "gcst_id is required"}), 400)

    if not file_type:
        return make_response(jsonify({"error": "file_type is required"}), 400)

    # normalise gcst_ids to a list of strings
    if isinstance(raw_gcst_ids, str):
        gcst_ids = [raw_gcst_ids]
    elif isinstance(raw_gcst_ids, list):
        gcst_ids = raw_gcst_ids
    else:
        return make_response(
            jsonify({"error": "gcst_id must be a string or a list of strings"}), 400
        )
    
    # sanity check list content and batch size check
    gcst_ids = list(dict.fromkeys(
    gcst.strip() for gcst in gcst_ids
    if isinstance(gcst, str) and gcst.strip()
    ))

    if not gcst_ids:
        return make_response(jsonify({"error": "gcst_id list is empty"}), 400)
    
    MAX_BATCH = 1000  # tune as you like
    if len(gcst_ids) > MAX_BATCH:
        return make_response(
            jsonify({
                "error": (
                    f"Too many gcst_id values in one request "
                    f"({len(gcst_ids)} > {MAX_BATCH}). "
                    "Please split into smaller batches."
                )
            }),
            400,
        )
    
    # 3. Validate file_type
    valid_file_types = [ft.value for ft in config.FileType]
    if file_type not in valid_file_types:
        return make_response(
            jsonify(
                {
                    "error": f"""
                    Invalid file_type: '{file_type}'.
                    Allowed types are: {', '.join(valid_file_types)}
                    """
                }
            ),
            400,
        )
    
    # 4. connect to MongoDB and update file types
    try:
        mdb = MongoClient(
            config.MONGO_URI,
            config.MONGO_USER,
            config.MONGO_PASSWORD,
            config.MONGO_DB,
        )
    except Exception as e:
        logger.error(
            "Failed to initialise Mongo client: %s", e, exc_info=True
        )
        return make_response(
            jsonify({"error": "Internal database connection error"}), 500
        )
    
    results = []
    for gcst_id in gcst_ids:
        logger.info(
            f"Received request to update gcst_id='{gcst_id}' with file_type='{file_type}'"
        )

        try:
            update_result = mdb.update_file_type(gcst_id=gcst_id, file_type=file_type)
        except Exception as e:
            logger.error(
                f"""
                An unexpected error occurred while updating file type
                for gcst_id='{gcst_id}': {e}
                """,
                exc_info=True,
            )
            results.append(
                {
                    "gcst_id": gcst_id,
                    "file_type": file_type,
                    "success": False,
                    "message": "An unexpected internal server error occurred.",
                }
            )
            continue

        if update_result is None or not update_result.get("success"):
            error_message = (
                update_result.get("message", "An error occurred during the update.")
                if update_result
                else "An unknown error occurred during the update."
            )
            logger.error(
                f"Update file type failed for gcst_id='{gcst_id}'. Reason: {error_message}"
            )
            results.append(
                {
                    "gcst_id": gcst_id,
                    "file_type": file_type,
                    "success": False,
                    "message": error_message,
                }
            )
        else:
            results.append(
                {
                    "gcst_id": gcst_id,
                    "file_type": file_type,
                    "success": True,
                    "message": update_result["message"],
                }
            )
    
    # 5. Decide top-level status
    all_ok = all(r["success"] for r in results)
    success_gcst_ids = [r["gcst_id"] for r in results if r["success"]]
    failed_gcst_ids = [r["gcst_id"] for r in results if not r["success"]]

    response_body = {
        "file_type": file_type,
        "summary": {
            "total_requested_gcst_ids": len(gcst_ids),
            "succeeded": len(success_gcst_ids),
            "failed": len(failed_gcst_ids),
            "success_gcst_ids": success_gcst_ids,
            "failed_gcst_ids": failed_gcst_ids,
        },
        "results": results,
    }

    # 6. Launch tasks to regenerate metadata YAML for successful updates
    for result in results:
        if result["success"]:
            gcst_id = result["gcst_id"]
            logger.info(f"Launching metadata YAML regeneration for gcst_id='{gcst_id}'")
            try:
                convert_metadata_to_yaml.apply_async(
                    args=[gcst_id],
                    kwargs={"is_harmonised_included": True, "is_save": False},
                    queue=config.CELERY_QUEUE3,
                    retry=True,
                )
            except Exception as e:
                logger.error(
                    f"Failed to launch metadata YAML regeneration task for gcst_id='{gcst_id}': {e}",
                    exc_info=True,
                )

    # If everything succeeded, return 200.
    # If some failed, return 207 Multi-Status.
    status_code = 200 if all_ok else 207

    return make_response(jsonify(response_body), status_code)

# --- Globus methods --- #


@app.route("/v1/sum-stats/globus/mkdir", methods=["POST"])
def make_dir():
    logger.info(">> /v1/sum-stats/globus/mkdir")
    req_data = request.get_json()
    unique_id = req_data["uniqueID"]
    email = req_data["email"]
    globus_origin_id = None
    if globus.list_dir(unique_id) is None:  # if not already exists
        globus_origin_id = globus.mkdir(unique_id, email)
    if globus_origin_id:
        resp = {"globusOriginID": globus_origin_id}
        return make_response(jsonify(resp), 201)
    else:
        resp = {"error": "Account not linked to Globus"}
        return make_response(jsonify(resp), 200)


@app.route("/v1/sum-stats/globus/<unique_id>", methods=["DELETE"])
def deactivate_dir(unique_id):
    resp = {"unique_id": unique_id}
    logger.info(f">> DELETE /v1/sum-stats/globus/{unique_id}")
    status = au.delete_globus_endpoint(unique_id)
    logger.info(f">> {status=}")
    if status is False:
        logger.info("aborting...")
        abort(404)
    return make_response(jsonify(resp), status)


@app.route("/v1/sum-stats/globus/<unique_id>")
def get_dir_contents(unique_id):
    resp = {"unique_id": unique_id}
    data = globus.list_dir(unique_id)
    resp["data"] = data
    if data is None:
        abort(404)
    else:
        return make_response(jsonify(resp), 200)


# --- Celery tasks --- #
# postval --> app side worker queue
# preval --> compute cluster side worker queue
# metadata-yml-update --> dynamic metadata update queue


@celery.task(queue=config.CELERY_QUEUE2, options={"queue": config.CELERY_QUEUE2})
def process_studies(
    callback_id: str,
    file_type=None,
    minrows: Union[int, None] = None,
    forcevalid: bool = False,
    bypass: bool = False,
):
    logger.info(">>> [process_studies]")
    logger.info(f"{callback_id=} with {minrows=} {forcevalid=} {bypass=} {file_type=}")

    # get payload from db
    mdb = MongoClient(
        config.MONGO_URI,
        config.MONGO_USER,
        config.MONGO_PASSWORD,
        config.MONGO_DB,
    )
    content = mdb.get_payload(callback_id)

    if endpoints.create_studies(
        callback_id=callback_id, file_type=file_type, content=content
    ):
        logger.info(f"endpoints.create_studies: True for {callback_id=}")
        validate_files_in_background.apply_async(
            kwargs={
                "callback_id": callback_id,
                "minrows": minrows,
                "forcevalid": forcevalid,
                "bypass": bypass,
                "file_type": file_type,
            },
            link=store_validation_results.s(forcevalid),
            retry=True,
        )


@celery.task(queue=config.CELERY_QUEUE1, options={"queue": config.CELERY_QUEUE1})
def validate_files_in_background(
    callback_id: str,
    minrows: Union[int, None] = None,
    forcevalid: bool = False,
    bypass: bool = False,
    file_type: Union[str, None] = None,
):
    logger.info(">>> [validate_files_in_background]")
    mdb = MongoClient(
        config.MONGO_URI,
        config.MONGO_USER,
        config.MONGO_PASSWORD,
        config.MONGO_DB,
    )
    content = mdb.get_payload(callback_id)
    logger.info(f"{content=}")
    logger.info(f"{callback_id=} with {minrows=} {forcevalid=} {bypass=} {file_type=}")

    mdb.upsert_payload(
        callback_id=callback_id,
        status=config.ValidationStatus.IN_PROGRESS,
    )

    logger.info("calling store_validation_method")
    au.store_validation_method(callback_id=callback_id, bypass_validation=forcevalid)

    if bypass is True:
        logger.info("Bypassing the validation.")
        results = au.skip_validation_completely(
            callback_id=callback_id,
            content=content,
            file_type=file_type,
        )
        mdb.upsert_payload(
            callback_id=callback_id,
            status=config.ValidationStatus.SKIPPED,
        )
    else:
        logger.info("Validating files.")
        results = au.validate_files(
            callback_id=callback_id,
            content=content,
            minrows=minrows,
            forcevalid=forcevalid,
            file_type=file_type,
        )
        mdb.upsert_payload(
            callback_id=callback_id,
            status=config.ValidationStatus.COMPLETED,
        )

    return results


@celery.task(queue=config.CELERY_QUEUE2, options={"queue": config.CELERY_QUEUE2})
def store_validation_results(results, force_valid):
    logger.info(">>> [store_validation_results]")
    if results:
        logger.info("results: True")
        au.store_validation_results_in_db(results, force_valid)


@celery.task(queue=config.CELERY_QUEUE1, options={"queue": config.CELERY_QUEUE1})
def remove_payload_files(callback_id):
    logger.info(">>> [remove_payload_files]")
    au.remove_payload_files(callback_id)


@celery.task(queue=config.CELERY_QUEUE1, options={"queue": config.CELERY_QUEUE1})
def move_files_to_staging(resp):
    logger.info(">>> [move_files_to_staging]")
    return au.move_files_to_staging(resp)


# The task name is misleading but keeping it as it's hard-coded in Java side.
# while publishing to rabbitmq pass is_harmonised_included from db
# and is_save=False
@celery.task(queue=config.CELERY_QUEUE3, options={"queue": config.CELERY_QUEUE3})
def convert_metadata_to_yaml(gcst_id, **kwargs):
    logger.info(f">>> [convert_metadata_to_yaml] for {gcst_id=}")

    is_harmonised_included = kwargs.get("is_harmonised_included", True)
    is_save = kwargs.get("is_save", True)
    globus_endpoint_id = kwargs.get("globus_endpoint_id", None)

    logger.info(f">>>>>>>>>>>>>> {is_harmonised_included=}")
    logger.info(f">>>>>>>>>>>>>> {is_save=}")
    logger.info(f">>>>>>>>>>>>>> {globus_endpoint_id=}")

    mdb = MongoClient(
        config.MONGO_URI,
        config.MONGO_USER,
        config.MONGO_PASSWORD,
        config.MONGO_DB,
    )

    # Explicitly set otherwise in nightly cron scripts.
    try:
        if is_save:
            logger.info("is save true")
            return au.save_convert_metadata_to_yaml(
                gcst_id, is_harmonised_included, globus_endpoint_id
            )
        else:
            logger.info("is save false")
            au.convert_metadata_to_yaml(gcst_id, is_harmonised_included)

            globus_endpoint_id = mdb.get_globus_endpoint_id(gcst_id)
            logger.info(f"<<<<<<<< {globus_endpoint_id=}")
            if globus_endpoint_id:
                logger.info(f"Deleting {globus_endpoint_id}.")
                au.delete_globus_endpoint(globus_endpoint_id)
            else:
                logger.info(f"No globus endpoint id found for {gcst_id}.")
    except Exception as e:
        study_data = mdb.get_study(gcst_id=gcst_id)
        if study_data and study_data.get("summaryStatisticsFile", "") == config.NR:
            info = f"""Skipping {gcst_id=} hm: {is_harmonised_included}
            as summary statistics file=NR."""
            logger.info(info)
            mdb.insert_or_update_metadata_yaml_request(
                gcst_id=gcst_id,
                status=config.MetadataYamlStatus.SKIPPED,
                is_harmonised=is_harmonised_included,
                additional_info={"info": info},
            )
        else:
            logger.info(
                f"""Adding {gcst_id=} hm: {is_harmonised_included}
                to the task failures collection."""
            )
            mdb.insert_or_update_metadata_yaml_request(
                gcst_id=gcst_id,
                status=config.MetadataYamlStatus.FAILED,
                is_harmonised=is_harmonised_included,
                additional_info={"exception": str(e)},
            )


@celery.task(queue=config.CELERY_QUEUE1, options={"queue": config.CELERY_QUEUE1})
def delete_globus_endpoint(globus_endpoint_id):
    logger.info(f">>> [delete_globus_endpoint] for {globus_endpoint_id}")
    return au.delete_globus_endpoint(globus_endpoint_id)


@task_failure.connect
def task_failure_handler(sender=None, **kwargs) -> None:
    logger.info(">>> [task_failure_handler]")
    subject = f"Celery error in {sender.name}"
    message = """{einfo} Task was called with args:
                 {args} kwargs: {kwargs}.\n
                 Exception was raised:\n{exception}\n
                 Traceback:\n{traceback}
              """.format(
        **kwargs
    )

    if sender.name != "sumstats_service.app.convert_metadata_to_yaml":
        send_mail(subject=subject, message=message)
    else:
        args = kwargs.get("args", [])
        exception = kwargs.get("exception", "No exception info")
        gcst_id = args[0] if args else "Unknown GCST ID"
        is_hm = args[1] if args else "Unknown HM"

        # Save to MongoDB
        mdb = MongoClient(
            config.MONGO_URI,
            config.MONGO_USER,
            config.MONGO_PASSWORD,
            config.MONGO_DB,
        )
        study_data = mdb.get_study(gcst_id=gcst_id)
        if not study_data or study_data.get("summaryStatisticsFile", "") != config.NR:
            logger.info(f"Adding {gcst_id=} to the task failures collection")
            # mdb.insert_task_failure(gcst_id=gcst_id, exception=str(exception))
            mdb.insert_or_update_metadata_yaml_request(
                gcst_id=gcst_id,
                status=config.MetadataYamlStatus.FAILED,
                is_harmonised=is_hm,
                additional_info={"exception": str(exception)},
            )
        else:
            logger.info(f"Skipping {gcst_id=} hm: {is_hm} as it has no sumstats.")


if __name__ == "__main__":
    app.run()
