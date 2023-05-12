import json
from collections import OrderedDict
from sumstats_service.resources.error_classes import *
import sumstats_service.resources.api_utils as au§
import sumstats_service.config as config
from sumstats_service.resources.mongo_client import mongoClient


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


def create_studies(content, callback_id=None):
    if au.json_payload_to_db(content=content, callback_id=callback_id):
        return True
    return False


def generate_callback_id():
    callback_id = au.generate_callback_id()
    response = {"callbackID": callback_id}
    return json.dumps(response)


def update_sumstats(callback_id, content):
    updated_content = au.update_payload(callback_id, content)
    return updated_content


def get_content(callback_id: str) -> dict:
    """Get sumstats content

    Arguments:
        callback_id -- callback id

    Returns:
        dict of submission contents
    """
    mdb = mongoClient(config.MONGO_URI,
                      config.MONGO_USER,
                      config.MONGO_PASSWORD,
                      config.MONGO_DB)
    data = [i for i in mdb.study_collection.find({"callbackID": callback_id})]
    content = {"requestEntries": []}
    for i in data:
        content["requestEntries"].append({"id": i['studyID'],
                                          "filePath": i["filePath"],
                                          "md5": i["md5"],
                                          "assembly": i["assembly"],
                                          "readme": i["readme"],
                                          "entryUUID": i["entryUUID"]})
    return content
