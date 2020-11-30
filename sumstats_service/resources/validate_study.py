import json
import sumstats_service.resources.study_service as st
import argparse
import sys
import config
import os



def parse_payload(payload, studyid):
    study_meta = [i for i in payload['requestEntries'] if i['id'] == studyid]
    if len(study_meta) != 1:
        print("could not find only one matching study id in payload")
        return False
    return (study_meta[0]['filePath'], study_meta[0]['md5'], study_meta[0]['assembly'], study_meta[0]['readme'],  study_meta[0]['entryUUID'] )
    
    

def validate_study(callback_id, study_id, filepath, md5, assembly, readme, entryUUID, out=None, minrows=None):
    study = st.Study(callback_id=callback_id, study_id=study_id, file_path=filepath, md5=md5, assembly=assembly, readme=readme, entryUUID=entryUUID)
    study.validate_study(minrows)
    print(study.study_id, study.retrieved, study.data_valid, study.error_code)
    if study.data_valid != 1:
        sys.exit(1)
    else:
        sys.exit(0)
    

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


    filepath, md5, assembly, readme, entryUUID = parse_payload(content, args.id)
    validate_study(args.cid, args.id, filepath, md5, assembly, readme, entryUUID, args.out, args.minrows)


if __name__ == '__main__':
    main()
