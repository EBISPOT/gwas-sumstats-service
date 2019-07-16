import simplejson
import logging
from flask import request, url_for
from collections import OrderedDict
from resources.error_classes import *
import resources.study_service as st
from resources.sqlite_client import sqlClient
import resources.api_utils as au
import resources.payload as pl


def root():
    response = {
                '_links': OrderedDict([
                    ('sumstats', au.create_href('sumstats'))
                 ])
               }
    return simplejson.dumps(response)


def get_sumstats(callback_id):
    payload = pl.Payload(callback_id=callback_id)
    status = payload.get_status_for_callback_id()
    # need to do this for each study in payload
    response = {"status"}
    return simplejson.dumps(response)


def create_studies(content):
    payload = pl.Payload(payload=content)
    payload.check_basic_content_present()
    payload.create_study_obj_list()
    payload.set_callback_id_for_studies()
    payload.create_entry_for_studies()
    response = {"callbackID": payload.callback_id}
    return simplejson.dumps(response)
