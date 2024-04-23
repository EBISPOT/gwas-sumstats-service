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
from sumstats_service.resources.error_classes import *
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
app.config[
    "CELERY_RESULT_BACKEND"
] = "rpc://"  #'{0}://guest@{1}:{2}'.format(config.BROKER, config.BROKER_HOST, config.BROKER_PORT)
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

    # option to allow zero p values
    zero_p_values = au.val_from_dict(key="zeroPvalue", dict=content, default=False)

    # option to bypass all validation and downstream steps
    bypass = au.val_from_dict(key="skipValidation", dict=content, default=False)

    file_type = au.determine_file_type(is_in_file=True, is_bypass=bypass)

    logger.info(f"{minrows=} {force_valid=} {zero_p_values=} {bypass=} {file_type=}")

    process_studies.apply_async(
        kwargs={
            "callback_id": callback_id,
            "content": content,
            "file_type": file_type,
            "minrows": minrows,
            "forcevalid": force_valid,
            "zero_p_values": zero_p_values,
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
    # option to allow zero p values
    zero_p_values = au.val_from_dict(key="zeroPvalue", dict=body, default=False)
    minrows = None if force_valid is True else minrows
    content = endpoints.get_content(callback_id)
    # reset validation status
    au.reset_validation_status(callback_id=callback_id)
    # run validation

    # option to bypass all validation and downstream steps
    bypass = au.val_from_dict(key="skipValidation", dict=body, default=False)

    # determine file_type
    template = au.get_template(callback_id)
    file_type = au.determine_file_type(is_in_file=bool(template), is_bypass=bypass)

    validate_files_in_background.apply_async(
        kwargs={
            "callback_id": callback_id,
            "content": content,
            "minrows": minrows,
            "forcevalid": force_valid,
            "bypass": bypass,
            "zero_p_values": zero_p_values,
            "file_type": file_type,
        },
        link=store_validation_results.s(),
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


# TODO: refactor this
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
                    logger.info('Task move_files_result ready.')
                    break
                logger.info(f"Waiting for move_files_result task to complete. Current state: {move_files_result.state}")
                time.sleep(10)
            else:
                raise Exception("Task move_files_result did not complete within the expected time.")

            if move_files_result.successful():
                logger.info(f"{callback_id=} :: move_files_result successful")
                metadata_conversion_result = convert_metadata_to_yaml.apply_async(
                    args=[resp["studyList"][0]["gcst"], False],
                    retry=True,
                )

                while (time.time() - start_time) < timeout:
                    if metadata_conversion_result.ready():
                        logger.info('Task metadata_conversion_result ready.')
                        break
                    logger.info(f"Waiting for metadata_conversion_result task to complete. Current state: {metadata_conversion_result.state}")
                    time.sleep(10)
                else:
                    raise Exception("Task metadata_conversion_result did not complete within the expected time.")

                if metadata_conversion_result.successful():
                    globus_endpoint_id = move_files_result.get()["globus_endpoint_id"]
                    logger.info(f">> [delete_globus_endpoint] calling {globus_endpoint_id=}")
                    delete_endpoint_result = au.delete_globus_endpoint(globus_endpoint_id)
                    logger.info(f"{callback_id=} :: {delete_endpoint_result=}")
                else:
                    raise Exception("Task metadata_conversion_result did not complete within the expected time.")
            else:
                raise Exception("Task move_files_result did not complete within the expected time.")
        except Exception as e:
            logger.error(f"{callback_id=} :: Error {e=}")
            return Response(status=500, mimetype="application/json")

    logger.info(f"{callback_id=} :: Return status 200")
    return Response(status=200, mimetype="application/json")


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
        logger.info('aborting...')
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
# metadata-yml-update-sandbox --> dynamic metadata update queue


@celery.task(queue=config.CELERY_QUEUE2, options={"queue": config.CELERY_QUEUE2})
def process_studies(
    callback_id: str,
    content: dict,
    file_type=None,
    minrows: Union[int, None] = None,
    forcevalid: bool = False,
    zero_p_values: bool = False,
    bypass: bool = False,
):
    logger.info(f">>> [process_studies] {callback_id=} with {minrows=} {forcevalid=} {bypass=} {zero_p_values=} {file_type=}")
    if endpoints.create_studies(callback_id=callback_id, file_type=file_type, content=content):
        logger.info(f'endpoints.create_studies: True for {callback_id=}')
        validate_files_in_background.apply_async(
            kwargs={
                "callback_id": callback_id,
                "content": content,
                "minrows": minrows,
                "forcevalid": forcevalid,
                "bypass": bypass,
                "zero_p_values": zero_p_values,
                "file_type": file_type,
            },
            link=store_validation_results.s(),
            retry=True,
        )


@celery.task(queue=config.CELERY_QUEUE1, options={"queue": config.CELERY_QUEUE1})
def validate_files_in_background(
    callback_id: str,
    content: dict,
    minrows: Union[int, None] = None,
    forcevalid: bool = False,
    bypass: bool = False,
    zero_p_values: bool = False,
    file_type: Union[str, None] = None,
):
    logger.info(f">>> [validate_files_in_background] {callback_id=} with {minrows=} {forcevalid=} {bypass=} {zero_p_values=} {file_type=}")

    logger.info('calling store_validation_method')
    au.store_validation_method(callback_id=callback_id, bypass_validation=forcevalid)

    if bypass is True:
        logger.info('Bypassing the validation.')
        results = au.skip_validation_completely(
            callback_id=callback_id, 
            content=content, 
            file_type=file_type,
        )
    else:
        logger.info('Validating files.')
        results = au.validate_files(
            callback_id=callback_id,
            content=content,
            minrows=minrows,
            forcevalid=forcevalid,
            zero_p_values=zero_p_values,
            file_type=file_type,
        )
    return results


@celery.task(queue=config.CELERY_QUEUE2, options={"queue": config.CELERY_QUEUE2})
def store_validation_results(results):
    logger.info(">>> [store_validation_results]")
    if results:
        logger.info('results: True')
        au.store_validation_results_in_db(results)


@celery.task(queue=config.CELERY_QUEUE1, options={"queue": config.CELERY_QUEUE1})
def remove_payload_files(callback_id):
    logger.info(">>> [remove_payload_files]")
    au.remove_payload_files(callback_id)


@celery.task(queue=config.CELERY_QUEUE1, options={"queue": config.CELERY_QUEUE1})
def move_files_to_staging(resp):
    logger.info(">>> [move_files_to_staging]")
    return au.move_files_to_staging(resp)


@celery.task(queue=config.CELERY_QUEUE3, options={"queue": config.CELERY_QUEUE3})
def convert_metadata_to_yaml(gcst_id, is_harmonised_included=True):
    logger.info(f">>> [convert_metadata_to_yaml] for {gcst_id=}")
    return au.convert_metadata_to_yaml(gcst_id, is_harmonised_included)


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
    send_mail(subject=subject, message=message)


if __name__ == "__main__":
    app.run()
