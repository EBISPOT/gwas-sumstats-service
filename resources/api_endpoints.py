import json
import logging
from flask import request, url_for
from collections import OrderedDict
from resources.error_classes import *
import resources.api_utils as au


def root():
    response = {
                '_links': OrderedDict([
                    ('sumstats', au.create_href('sumstats'))
                 ])
               }
    return json.dumps(response)


def get_sumstats(callback_id):
    response = au.construct_get_payload_response(callback_id)
    return json.dumps(response)


def create_studies(content):
    callback_id = au.json_payload_to_db(content)
    response = {"callbackID": callback_id}
    return json.dumps(response)
