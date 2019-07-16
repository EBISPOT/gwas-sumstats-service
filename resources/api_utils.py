from urllib.parse import unquote
from flask import url_for
import config
from resources.error_classes import *
import resources.study_service as st
from resources.sqlite_client import sqlClient




def create_href(method_name, params=None):
    params = params or {}
    params['_external'] = True
    return {'href': unquote(
        url_for(method_name, **params)
    )}


def get_status_for_callback_id(callback_id):
    sq = sqlClient(config.DB_PATH)
    data = sq.get_data_from_callback_id(callback_id)
    if data is None:
        raise RequestedNotFound("Couldn't find resource with callback id: {}".format(callback_id))
    for row in data:
        study_id, callback_id, pmid, file_path, md5, assembly, retrieved, data_valid = row
        if retrieved == None and data_valid == None:
            return 'VALIDATING'


    
    
