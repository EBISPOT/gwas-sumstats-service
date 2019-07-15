import simplejson
import logging
from flask import request, url_for
from collections import OrderedDict
from resources.error_classes import *
import resources.study_controller as sc
import resources.api_utils as au


def root():
    response = {
                '_links': OrderedDict([
                    ('studies', au.create_href('studies'))
                 ])
               }
    return simplejson.dumps(response)


def get_studies():
    response = {}
    return simplejson.dumps(response)


def create_studies(content):
    callback_id = None
    if not 'requestEntries' in content:
        raise BadUserRequest("Missing 'requestEntries' in json")
    if len(content['requestEntries']) == 0:
        raise BadUserRequest("Missing data")
    for item in content['requestEntries']:
        study_id, pmid, file_path, md5, assembly = au.parse_new_study_json(item)
        study = sc.Study(study_id=study_id, pmid=pmid, file_path=file_path, md5=md5, assembly=assembly)
        print(study.study_id)
        if not study.valid_study_id():
            raise BadUserRequest("Study ID: {} is invalid")
        if study.study_id_exists_in_db():
            raise BadUserRequest("Study ID: {} exists already")
    callback_id = au.generate_callback_id()
    response = {"callbackID": callback_id}
    return simplejson.dumps(response)
