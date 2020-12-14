import json
import sumstats_service.resources.payload as pl
import argparse
import sys
import config
import os



def validate_metadata_for_payload(callback_id, content):
    payload = pl.Payload(callback_id=callback_id, payload=content)
    payload.create_study_obj_list()
    payload.set_callback_id_for_studies()
    payload.validate_payload_metadata()
    response = construct_validation_response(callback_id, payload)
    return json.dumps(response)



def validate_files_from_payload(callback_id, content, out=None, minrows=None):
    payload = pl.Payload(callback_id=callback_id, payload=content)
    payload.create_study_obj_list()
    payload.set_callback_id_for_studies()
    payload.validate_payload(minrows=minrows)
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
              "errorCode": 10
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


def is_json(string):
  try:
    json_object = json.loads(string)
  except ValueError as e:
    return False
  return True

def is_path(string):
    try:
        path_object = os.path.isfile(string)
        return path_object
    except TypeError as e:
        return False


def move_to_valid(callback_id, content):
    payload = pl.Payload(callback_id=callback_id, payload=content)
    payload.create_study_obj_list()
    payload.set_callback_id_for_studies()    
    for study in payload.study_obj_list:
        study.move_to_valid()


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("-cid", help='The callback ID', required=True)
    argparser.add_argument("-payload", help='JSON payload (input)', required=True)
    argparser.add_argument("-out", help='JSON output file (e.g. SOME_ID.json)', required=False, default='validation.json')
    argparser.add_argument("-storepath", help='The storage path you want the data written to e.g. /path/to/data', required=False, default=config.STORAGE_PATH)
    argparser.add_argument("-validated_path", help='The path you want the validated files written to e.g. /path/to/data', required=False, default=config.VALIDATED_PATH)
    argparser.add_argument("-ftpserver", help='The FTP server name where your files are', required=False, default=config.FTP_SERVER)
    argparser.add_argument("-ftpuser", help='The FTP username', required=False, default=config.FTP_USERNAME)
    argparser.add_argument("-ftppass", help='The FTP password', required=False, default=config.FTP_PASSWORD)
    argparser.add_argument("-minrows", help='The minimum required rows in a sumsats file for validation to pass', required=False, default=None)
    argparser.add_argument("-metadata", help='Validate the metadata only', required=False, action='store_true', dest='meta_only')
    argparser.add_argument("-move_files", help='Just move the files', required=False, action='store_true')
    
    
    args = argparser.parse_args()
    if args.storepath:
        config.STORAGE_PATH = args.storepath
    if args.validated_path:
        config.VALIDATED_PATH = args.validated_path
    if args.ftpserver:
        config.FTP_SERVER = args.ftpserver
    if args.ftpuser:
        config.FTP_USERNAME = args.ftpuser
    if args.ftppass:
        config.FTP_PASSWORD = args.ftppass

    if is_path(args.payload):
        with open(args.payload, "r") as f:
            content = json.load(f)
    else:
        # if content is given as json string
        content = json.loads(args.payload)

    if args.meta_only is True:
        validate_metadata_for_payload(args.cid, content, args.out, args.minrows)
    elif args.move_files is True:
        move_to_valid(args.cid, content)
    else:
        validate_files_from_payload(args.cid, content, args.out, args.minrows)


if __name__ == '__main__':
    main()
