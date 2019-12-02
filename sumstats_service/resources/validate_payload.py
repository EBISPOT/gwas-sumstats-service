import json
import sumstats_service.resources.payload as pl
import argparse
import sys
import config


def validate_files_from_payload(callback_id, content, out=None):
    payload = pl.Payload(callback_id=callback_id, payload=content)
    payload.create_study_obj_list()
    payload.set_callback_id_for_studies()
    payload.validate_payload()
    response = construct_validation_response(callback_id, payload)
    if out:
        with open(out, 'w') as out:
            out.write(json.dumps(response))
    return json.dumps(response)


def construct_validation_response(callback_id, payload):
    validation_list = []
    for study in payload.study_obj_list:
        validation_report = create_validation_report(study)
        validation_list.append(validation_report)
    response = {"callbackID": str(callback_id),
                "validationList": validation_list
                }
    return response


def construct_failure_response(callback_id, payload):
    validation_list = []
    for study in payload.study_obj_list:
        validation_report = {
              "id": study.study_id,
              "retrieved": "",
              "dataValid": "",
              "errorCode": "An error occurred in the validation process, please contact us"
              }

        validation_list.append(validation_report)
    response = {"callbackID": str(callback_id),
                "validationList": validation_list
                }
    return response


def create_validation_report(study):
    report = {
              "id": study.study_id,
              "retrieved": study.retrieved,
              "dataValid": study.data_valid,
              "errorCode": study.error_code
              }
    return report


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("-cid", help='The callback ID', required=True)
    argparser.add_argument("-payload", help='JSON payload (input)', required=True)
    argparser.add_argument("-out", help='JSON output file (e.g. SOME_ID.json)', required=False, default='validation.json')
    argparser.add_argument("-storepath", help='The storage path you want the data written to e.g. /path/to/data', required=False, default=config.STORAGE_PATH)
    
    args = argparser.parse_args()
    if args.storepath:
        config.STORAGE_PATH = args.storepath

    validate_files_from_payload(args.cid, json.loads(args.payload), args.out)


if __name__ == '__main__':
    main()
