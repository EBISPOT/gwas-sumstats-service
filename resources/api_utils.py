from urllib.parse import unquote
from flask import url_for
import config
from resources.error_classes import *
import resources.study_service as st
from resources.sqlite_client import sqlClient
import resources.payload as pl



def create_href(method_name, params=None):
    params = params or {}
    params['_external'] = True
    return {'href': unquote(
        url_for(method_name, **params)
    )}

def json_payload_to_db(content):
    payload = pl.Payload(payload=content)
    payload.check_basic_content_present()
    payload.create_study_obj_list()
    payload.set_callback_id_for_studies()
    payload.create_entry_for_studies()



    
    
