import json
import sumstats_service.resources.study_service as st
import sumstats_service.resources.payload as pl
import sumstats_service.resources.utils as utils
import argparse
import sys
import config
import os


def validate_study(callback_id, study_id, filepath, md5, assembly, readme, entryUUID, out=None, minrows=None, forcevalid=False):
    study = st.Study(callback_id=callback_id, study_id=study_id, file_path=filepath, md5=md5, assembly=assembly, readme=readme, entryUUID=entryUUID)
    study.validate_study(minrows=minrows, forcevalid=forcevalid)
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
    argparser.add_argument("-forcevalid", help='Setting to True will force the validation to be true', type=utils.str2bool, nargs='?', const=True, required=False, default=False)

    
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

    if utils.is_path(args.payload):
        with open(args.payload, "r") as f:
            content = json.load(f)
    else:
        # if content is given as json string
        content = json.loads(args.payload)


    filepath, md5, assembly, readme, entryUUID = pl.parse_payload(content, args.id, args.cid)
    minrows = None if len(args.minrows) == 0 or args.minrows == "None" else args.minrows
    validate_study(args.cid, args.id, filepath, md5, assembly, readme, entryUUID, args.out, minrows, args.forcevalid)


if __name__ == '__main__':
    main()
