import os
import base64
from urllib.parse import unquote
from flask import url_for
import config
from resources.error_classes import *
import resources.study_service as st
from resources.sqlite_client import sqlClient


def parse_new_study_json(study):
    """
    Expecting:
    {
       "id": "xyz321",
       "pmid": "1233454",
       "filePath": "file/path.tsv",
       "md5":"b1d7e0a58d36502d59d036a17336ddf5",
       "assembly":"38"
    }
    """
    try:
        study_id = study['id']
        pmid = study['pmid']
        file_path = study['filePath']
        md5 = study['md5']
        assembly = study['assembly']
    except KeyError as e:
        raise BadUserRequest("Missing field: {} in json".format(str(e)))
    return (study_id, pmid, file_path, md5, assembly)


def create_href(method_name, params=None):
    params = params or {}
    params['_external'] = True
    return {'href': unquote(
        url_for(method_name, **params)
    )}


def generate_callback_id():
    randid = base64.b64encode(os.urandom(32))[:8]
    sq = sqlClient(config.DB_PATH)
    while sq.get_data_from_callback_id(randid) is not None:
        randid = base64.b64encode(os.urandom(32))[:8]
    return randid


def check_basic_content_present(content):
    if not 'requestEntries' in content:
        raise BadUserRequest("Missing 'requestEntries' in json")
    if len(content['requestEntries']) == 0:
        raise BadUserRequest("Missing data")
    return True


def check_study_ids_ok(content):
    study_list = []
    for item in content['requestEntries']:
        study_id, pmid, file_path, md5, assembly = parse_new_study_json(item)
        study = st.Study(study_id=study_id, pmid=pmid, 
                         file_path=file_path, md5=md5, 
                         assembly=assembly)
        if not study.valid_study_id():
            raise BadUserRequest("Study ID: {} is invalid".format(study_id))
        if study.study_id_exists_in_db():
            raise BadUserRequest("Study ID: {} exists already".format(study_id))
        if study_id not in study_list:
            study_list.append(study_id)
        else:
            raise BadUserRequest("Study ID: {} duplicated in payload".format(study_id))
    return True
    
