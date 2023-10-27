import argparse
import json
import logging
import os
import sys

import sumstats_service.resources.payload as pl
import sumstats_service.resources.study_service as st
from sumstats_service import config

logging.basicConfig(level=logging.DEBUG, format="(%(levelname)s): %(message)s")
logger = logging.getLogger(__name__)


def parse_payload(content, studyid, callback_id):
    payload = pl.Payload(callback_id=callback_id, payload=content)
    payload.create_study_obj_list()
    payload.set_callback_id_for_studies()
    study_meta = [s for s in payload.study_obj_list if s.study_id == studyid]
    if len(study_meta) != 1:
        print("could not find only one matching study id in payload")
        return False
    return (
        study_meta[0].file_path,
        study_meta[0].md5,
        study_meta[0].assembly,
        study_meta[0].readme,
        study_meta[0].entryUUID,
    )


def validate_study(
    callback_id,
    study_id,
    filepath,
    md5,
    assembly,
    readme,
    entryUUID,
    out=None,
    minrows=None,
    forcevalid=False,
    zero_p_values=False,
):
    logger.info("validating study data")
    print('[[[[[[[[[[[[[[validate_study]]]]]]]]]]]]]]')
    study = st.Study(
        callback_id=callback_id,
        study_id=study_id,
        file_path=filepath,
        md5=md5,
        assembly=assembly,
        readme=readme,
        entryUUID=entryUUID,
    )
    study.validate_study(
        minrows=minrows, forcevalid=forcevalid, zero_p_values=zero_p_values
    )
    write_result(study, out)
    if study.data_valid != 1:
        sys.exit(1)
    else:
        sys.exit(0)


def copy_file_for_validation(
    callback_id, study_id, filepath, entryUUID, md5, assembly, out=None
):
    print('[[[[[[[[[[[[[[[[[[[03]]]]]]]]]]]]]]]]]]]')
    print(f'{callback_id=}')
    print(f'{study_id=}')
    print(f'{filepath=}')
    print(f'{entryUUID=}')
    print(f'{md5=}')
    print(f'{assembly=}')
    
    study = st.Study(
        callback_id=callback_id,
        study_id=study_id,
        file_path=filepath,
        entryUUID=entryUUID,
        md5=md5,
        assembly=assembly,
    )
    study.retrieve_study_file()
    if study.retrieved != 1:
        write_result(study, out)
        sys.exit(1)
    else:
        sys.exit(0)


def write_result(study, out):
    result = {
        "id": study.study_id,
        "retrieved": study.retrieved,
        "dataValid": study.data_valid,
        "errorCode": study.error_code,
    }
    logger.info("result obj: {}".format(json.dumps(result)))
    with open(out, "w") as f:
        f.write(json.dumps(result))


def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif v.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")


def is_path(string):
    try:
        path_object = os.path.isfile(string)
        return path_object
    except TypeError as e:
        return False


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("-cid", help="The callback ID", required=True)
    argparser.add_argument("-id", help="The ID of the study", required=True)
    argparser.add_argument("-payload", help="JSON payload (input)", required=True)
    argparser.add_argument(
        "-out",
        help="JSON output file (e.g. SOME_ID.json)",
        required=False,
        default="validation.json",
    )
    argparser.add_argument(
        "-storepath",
        help="The storage path you want the data written to e.g. /path/to/data",
        required=False,
        default=config.STORAGE_PATH,
    )
    argparser.add_argument(
        "-validated_path",
        help="The path you want the validated files written to e.g. /path/to/data",
        required=False,
        default=config.VALIDATED_PATH,
    )
    argparser.add_argument(
        "-depo_path",
        help="The path you want the submitted files written to e.g. /path/to/data",
        required=False,
        default=config.DEPO_PATH,
    )
    argparser.add_argument(
        "-ftpserver",
        help="The FTP server name where your files are",
        required=False,
        default=config.FTP_SERVER,
    )
    argparser.add_argument(
        "-ftpuser", help="The FTP username", required=False, default=config.FTP_USERNAME
    )
    argparser.add_argument(
        "-ftppass", help="The FTP password", required=False, default=config.FTP_PASSWORD
    )
    argparser.add_argument(
        "-minrows",
        help="The minimum required rows in a sumsats file for validation to pass",
        required=False,
        default=None,
    )
    argparser.add_argument(
        "-zero_p",
        help="Setting True will allow p_values to be zero",
        type=str2bool,
        nargs="?",
        const=True,
        required=False,
        default=False,
    )
    argparser.add_argument(
        "-forcevalid",
        help="Setting to True will force the validation to be true",
        type=str2bool,
        nargs="?",
        const=True,
        required=False,
        default=False,
    )
    argparser.add_argument(
        "--copy_only",
        help="Setting to True will only copy the file to the validation path",
        type=str2bool,
        nargs="?",
        const=True,
        required=False,
        default=False,
    )

    args = argparser.parse_args()
    if args.storepath:
        config.STORAGE_PATH = args.storepath
    if args.validated_path:
        config.VALIDATED_PATH = args.validated_path
    if args.depo_path:
        config.DEPO_PATH = args.depo_path
    if args.ftpserver:
        config.FTP_SERVER = args.ftpserver
    if args.ftpuser:
        config.FTP_USERNAME = args.ftpuser
    if args.ftppass:
        config.FTP_PASSWORD = args.ftppass

    print('==++' * 20)
    print(f'{args.payload=}')
    print(f'{is_path(args.payload)=}')
    print('=++=' * 20)

    with open(args.payload, "r") as f:
        content = json.load(f)

    # if is_path(args.payload):
    #     with open(args.payload, "r") as f:
    #         content = json.load(f)
    # else:
    #     # if content is given as json string
    #     content = json.loads(args.payload)

    filepath, md5, assembly, readme, entryUUID = parse_payload(
        content, args.id, args.cid
    )
    out = os.path.join(args.validated_path, args.cid, args.out)
    logger.info(f"validation out json: {out}")

    print('[[[[[[[[[[[[[[[[[[[01]]]]]]]]]]]]]]]]]]]')
    print(f'{args.copy_only=}')
    print('[[[[[[[[[[[[[[[[[[[02]]]]]]]]]]]]]]]]]]]')

    if args.copy_only:
        copy_file_for_validation(
            callback_id=args.cid,
            study_id=args.id,
            filepath=filepath,
            entryUUID=entryUUID,
            md5=md5,
            assembly=assembly,
            out=out,
        )
    else:
        minrows = (
            None if len(args.minrows) == 0 or args.minrows == "None" else args.minrows
        )

        print(f'{minrows=}')
        print(f'{args.cid=}')
        print(f'{args.id=}')
        print(f'{filepath=}')
        print(f'{md5=}')
        print(f'{assembly=}')
        print(f'{entryUUID=}')
        print(f'{out=}')
        print(f'{args.forcevalid=}')
        print(f'{args.zero_p=}')

        validate_study(
            args.cid,
            args.id,
            filepath,
            md5,
            assembly,
            readme,
            entryUUID,
            out,
            minrows,
            args.forcevalid,
            args.zero_p,
        )


if __name__ == "__main__":
    main()
