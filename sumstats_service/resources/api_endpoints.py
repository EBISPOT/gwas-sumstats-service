import json
from collections import OrderedDict
from sumstats_service.resources.error_classes import *
import sumstats_service.resources.api_utils as au


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

def delete_sumstats(callback_id):
    response = au.delete_payload_from_db(callback_id)
    return json.dumps(response)

def create_studies(content):
    callback_id = au.json_payload_to_db(content)
    response = {"callbackID": callback_id}
    return json.dumps(response)
