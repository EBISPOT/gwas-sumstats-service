import json
import sumstats_service.resources.study_service as st
import sumstats_service.resources.payload as pl
import argparse
import sys
import config
import os



def parse_payload(content, studyid, callback_id):
    payload = pl.Payload(callback_id=callback_id, payload=content)
    payload.create_study_obj_list()
    payload.set_callback_id_for_studies()
    study_meta = [s for s in payload.study_obj_list if s.study_id == studyid]
    if len(study_meta) != 1:
        print("could not find only one matching study id in payload")
        return False
    return (study_meta[0].file_path, study_meta[0].md5, study_meta[0].assembly, study_meta[0].readme,  study_meta[0].entryUUID )
    
    
def validate_study(callback_id, study_id, filepath, md5, assembly, readme, entryUUID, out=None, minrows=None):
    study = st.Study(callback_id=callback_id, study_id=study_id, file_path=filepath, md5=md5, assembly=assembly, readme=readme, entryUUID=entryUUID)
    study.validate_study(minrows)
    result = { 
                "id": study.study_id,
                "retrieved": study.retrieved,
                "dataValid": study.data_valid,
                "errorCode": study.error_code
             }
    print(result)
    if out:           
        with open(out, 'w') as f:
            f.write(json.dumps(result))
    if study.data_valid != 1:
        sys.exit(1)
    else:
        sys.exit(0)



def force_valid(callback_id, study_id, filepath, md5, assembly, readme, entryUUID):
    study = st.Study(callback_id=callback_id, study_id=study_id, file_path=filepath, md5=md5, assembly=assembly, readme=readme, entryUUID=entryUUID)
    study.force_valid()
    

def is_path(string):
    try:
        path_object = os.path.isfile(string)
        return path_object
    except TypeError as e:
        return False

def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("-cid", help='The callback ID', required=True)    
    argparser.add_argument("-id", help='The ID of the study', required=True)
    argparser.add_argument("-payload", help='JSON payload (input)', required=True)
    argparser.add_argument("-out", help='JSON output file (e.g. SOME_ID.json)', required=False, default='validation.json')
    argparser.add_argument("-storepath", help='The storage path you want the data written to e.g. /path/to/data', required=False, default=config.STORAGE_PATH)
    argparser.add_argument("-validated_path", help='The path you want the validated files written to e.g. /path/to/data', required=False, default=config.VALIDATED_PATH)
    argparser.add_argument("-ftpserver", help='The FTP server name where your files are', required=False, default=config.FTP_SERVER)
    argparser.add_argument("-ftpuser", help='The FTP username', required=False, default=config.FTP_USERNAME)
    argparser.add_argument("-ftppass", help='The FTP password', required=False, default=config.FTP_PASSWORD)
    argparser.add_argument("-minrows", help='The minimum required rows in a sumsats file for validation to pass', required=False, default=None)
    argparser.add_argument("-force_valid", help='Force the validation to be true', required=False, action='store_true')
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


    out = os.path.join(args.storepath, args.cid, args.out)
    filepath, md5, assembly, readme, entryUUID = parse_payload(content, args.id, args.cid)
    minrows = None if len(args.minrows) == 0 or args.minrows == "None" else args.minrows
    if args.force_valid is True:
        force_valid(args.cid, args.id, filepath, md5, assembly, readme, entryUUID)
    else:
        validate_study(args.cid, args.id, filepath, md5, assembly, readme, entryUUID, out, minrows)


if __name__ == '__main__':
    main()
