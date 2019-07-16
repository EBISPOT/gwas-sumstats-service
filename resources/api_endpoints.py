import simplejson
import logging
from flask import request, url_for
from collections import OrderedDict
from resources.error_classes import *
import resources.study_service as st
import resources.api_utils as au


def root():
    response = {
                '_links': OrderedDict([
                    ('sumstats', au.create_href('sumstats'))
                 ])
               }
    return simplejson.dumps(response)


def get_sumstats():
    response = {}
    return simplejson.dumps(response)


def create_studies(content):
    callback_id = None
    au.check_basic_content_present(content)
    au.check_study_ids_ok(content)
    callback_id = au.generate_callback_id()
    for item in content['requestEntries']:
        study_id, pmid, file_path, md5, assembly = au.parse_new_study_json(item)
        study = st.Study(study_id=study_id, pmid=pmid, 
                         file_path=file_path, md5=md5, 
                         assembly=assembly, callback_id=callback_id)
        study.create_entry_for_study()
    response = {"callbackID": callback_id}
    return simplejson.dumps(response)
