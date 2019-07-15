import os
import base64
from urllib.parse import unquote
from flask import url_for
import config
from resources.error_classes import *
from resources.sqlite_client import sqlClient


def parse_new_study_json(study):
    """
    Expecting:
    {
       "id": "xyz321",
       "pmid": "1233454",
       "NOT_filePath": "file/path.tsv",
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
    except KeyError:
        raise BadUserRequest("Missing field in json")
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
    while sq.get_data_from_callback_id(randid) is not False:
        randid = base64.b64encode(os.urandom(32))[:8]
    return randid
    

