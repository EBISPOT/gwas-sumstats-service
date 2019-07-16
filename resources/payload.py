import os
import base64
from resources.sqlite_client import sqlClient
from resources.error_classes import *
import resources.study_service as st
import config


class Payload:
    def __init__(self, payload=None):
        self.payload = payload
        self.callback_id = None
        self.study_list = []
        self.study_ids = []

    def check_basic_content_present(self):
        if not 'requestEntries' in self.payload:
            raise BadUserRequest("Missing 'requestEntries' in json")
        if len(self.payload['requestEntries']) == 0:
            raise BadUserRequest("Missing data")
        return True

    def check_study_ids_ok(self):
        for item in self.payload['requestEntries']:
            study_id, pmid, file_path, md5, assembly = self.parse_new_study_json(item)
            study = st.Study(study_id=study_id, pmid=pmid, 
                             file_path=file_path, md5=md5, 
                             assembly=assembly)
            if not study.valid_study_id():
                raise BadUserRequest("Study ID: {} is invalid".format(study_id))
            if study.study_id_exists_in_db():
                raise BadUserRequest("Study ID: {} exists already".format(study_id))
            if study.study_id not in self.study_ids:
                self.study_ids.append(study.study_id)
                self.study_list.append(study)
            else:
                raise BadUserRequest("Study ID: {} duplicated in payload".format(study_id))
        return True

    def generate_callback_id(self):
        randid = base64.b64encode(os.urandom(32))[:8]
        sq = sqlClient(config.DB_PATH)
        while sq.get_data_from_callback_id(randid) is not None:
            randid = base64.b64encode(os.urandom(32))[:8]
        self.callback_id = randid

    def set_callback_id_for_studies(self):
        for study in self.study_list:
            study.callback_id = self.callback_id

    def create_entry_for_studies(self):
        self.set_callback_id_for_studies()
        for study in self.study_list:
            study.create_entry_for_study()

    @staticmethod
    def parse_new_study_json(study_dict):
        """
        Expecting:
        {
           "id": "xyz321",
           "pmid": "1233454",
           "filePath": "file/path.tsv",
           "md5":"b1d7e0a58d36502d59d036a17336ddf5",
           "assembly":"38"
        }
        """
        try:
            study_id = study_dict['id']
            pmid = study_dict['pmid']
            file_path = study_dict['filePath']
            md5 = study_dict['md5']
            assembly = study_dict['assembly']
        except KeyError as e:
            raise BadUserRequest("Missing field: {} in json".format(str(e)))
        return (study_id, pmid, file_path, md5, assembly)

