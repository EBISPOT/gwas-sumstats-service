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




    
    
