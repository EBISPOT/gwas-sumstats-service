import shortuuid
import json
import argparse
from sumstats_service.resources.mongo_client import mongoClient
from sumstats_service.resources.error_classes import *
import sumstats_service.resources.study_service as st
import sumstats_service.resources.file_handler as fh
import sumstats_service.resources.utils as utils
import config


class Payload:
    def __init__(self, payload=None, callback_id=None):
        self.payload = payload
        self.callback_id = callback_id
        self.study_obj_list = []
        self.study_ids = []
        self.metadata_errors = []

    def payload_to_db(self):
        if self.check_basic_content_present() is True:
            self.create_study_obj_list()
            if self.check_study_ids_valid() is True:
                self.set_callback_id_for_studies()
                self.create_entry_for_studies()
        self.store_metadata_errors()

    def validate_payload(self, minrows=None):
        for study in self.study_obj_list:
            study.validate_study(minrows)


    def validate_payload_metadata(self):
        for study in self.study_obj_list:
            study.mandatory_metadata_check()
            

    def get_payload_status(self):
        study_statuses = [study.get_status() for study in self.study_obj_list]
        if 'INVALID' in study_statuses:
            return 'INVALID'
        elif 'RETRIEVING' in study_statuses:
            return 'PROCESSING'
        else:
            return 'VALID'


    def get_data_for_callback_id(self):
        mdb = mongoClient(config.MONGO_URI, config.MONGO_USER, config.MONGO_PASSWORD, config.MONGO_DB)
        data = mdb.get_data_from_callback_id(self.callback_id)
        self.get_metadata_errors()
        if data is None:
            if mdb.check_callback_id_in_db(self.callback_id):
                # callback registered but studies not yet added (due to async)
                return True
            else:
                raise RequestedNotFound("Couldn't find resource with callback id: {}".format(self.callback_id))

        for study_metadata in data:
            study_id = st.set_var_from_dict(study_metadata, 'studyID', None)
            callback_id = st.set_var_from_dict(study_metadata, 'callbackID', None)
            file_path = st.set_var_from_dict(study_metadata, 'filePath', None)
            md5 = st.set_var_from_dict(study_metadata, 'md5', None)
            assembly = st.set_var_from_dict(study_metadata, 'assembly', None)
            retrieved = st.set_var_from_dict(study_metadata, 'retrieved', None) 
            data_valid = st.set_var_from_dict(study_metadata, 'dataValid', None)
            error_code = st.set_var_from_dict(study_metadata, 'errorCode', None)
            readme = st.set_var_from_dict(study_metadata, 'readme', None)
            entryUUID = st.set_var_from_dict(study_metadata, 'entryUUID', None)
            author_name = st.set_var_from_dict(study_metadata, 'authorName', None)
            pmid = st.set_var_from_dict(study_metadata, 'pmid', None)
            gcst = st.set_var_from_dict(study_metadata, 'gcst', None)
            raw_ss= st.set_var_from_dict(study_metadata, 'rawSS', None)

            study = st.Study(study_id=study_id, callback_id=callback_id, file_path=file_path, 
                            md5=md5, assembly=assembly, retrieved=retrieved,
                            data_valid=data_valid, error_code=error_code, readme=readme, 
                            entryUUID=entryUUID, author_name=author_name, pmid=pmid, gcst=gcst, raw_ss=raw_ss)
            self.study_obj_list.append(study)
        return self.study_obj_list

    def remove_callback_id(self):
        mdb = mongoClient(config.MONGO_URI, config.MONGO_USER, config.MONGO_PASSWORD, config.MONGO_DB)
        mdb.remove_callback_id(self.callback_id)
        
    def store_metadata_errors(self):
        mdb = mongoClient(config.MONGO_URI, config.MONGO_USER, config.MONGO_PASSWORD, config.MONGO_DB)
        mdb.update_metadata_errors(self.callback_id, self.metadata_errors)

    def get_metadata_errors(self):
        mdb = mongoClient(config.MONGO_URI, config.MONGO_USER, config.MONGO_PASSWORD, config.MONGO_DB)
        self.metadata_errors = mdb.get_metadata_errors(self.callback_id)


    def check_basic_content_present(self):
        if not 'requestEntries' in self.payload:
            self.metadata_errors.append("Missing 'requestEntries' in json")
            return False
            #raise BadUserRequest("Missing 'requestEntries' in json")
        elif len(self.payload['requestEntries']) == 0:
            self.metadata_errors.append("Missing data")
            return False
            #raise BadUserRequest("Missing data")
        return True

    def create_study_obj_list(self):
        for item in self.payload['requestEntries']:
            study_id, file_path, md5, assembly, readme, entryUUID, raw_file_path = self.parse_new_study_json(item)
            study = st.Study(study_id=study_id, file_path=file_path, md5=md5,
                             assembly=assembly, readme=readme, entryUUID=entryUUID, raw_ss=raw_file_path)
            self.study_obj_list.append(study)
        return True

    def check_study_ids_valid(self):
        for study in self.study_obj_list:
            if not study.valid_study_id():
                self.metadata_errors.append("Study ID: {} is invalid".format(study.study_id))
                #raise BadUserRequest("Study ID: {} is invalid".format(study.study_id))
                return False
            if study.study_id_exists_in_db():
                self.metadata_errors.append("Study ID: {} exists already".format(study.study_id))
                #raise BadUserRequest("Study ID: {} exists already".format(study.study_id))
                return False
            if study.study_id not in self.study_ids:
                self.study_ids.append(study.study_id)
            else:
                self.metadata_errors.append("Study ID: {} duplicated in payload".format(study.study_id))
                #raise BadUserRequest("Study ID: {} duplicated in payload".format(study.study_id))
                return False
        return True

    def generate_callback_id(self):
        randid = shortuuid.uuid()[:8]
        mdb = mongoClient(config.MONGO_URI, config.MONGO_USER, config.MONGO_PASSWORD, config.MONGO_DB)
        while mdb.check_callback_id_in_db(randid) is True:
            randid = shortuuid.uuid()[:8]
        self.callback_id = randid
        mdb.register_callback_id(self.callback_id)

    def set_callback_id_for_studies(self):
        if self.callback_id:
            for study in self.study_obj_list:
                study.callback_id = self.callback_id
        else:
            self.generate_callback_id()
            for study in self.study_obj_list:
                study.callback_id = self.callback_id

    def store_validation_results(self):
        for study in self.study_obj_list:
            study.store_validation_statuses()

    def create_entry_for_studies(self):
        for study in self.study_obj_list:
            study.create_entry_for_study()

    @staticmethod
    def parse_new_study_json(study_dict):
        """
        Expecting:
        {
           "id": "xyz321",
           "filePath": "file/path.tsv",
           "entryUUID": "abc789",
           "md5":"b1d7e0a58d36502d59d036a17336ddf5",
           "assembly":"38",
           "readme":"optional text",
           "rawFilePath": "optional/file/path.tsv"
        }
        """
        study_id = study_dict['id'] if 'id' in study_dict else None
        file_path = study_dict['filePath'] if 'filePath' in study_dict else None
        md5 = study_dict['md5'] if 'md5' in study_dict else None
        assembly = study_dict['assembly'] if 'assembly' in study_dict else None
        readme = study_dict['readme'] if 'readme' in study_dict else None     
        entryUUID = study_dict['entryUUID'] if 'entryUUID' in study_dict else None
        raw_file_path = study_dict['rawFilePath'] if 'rawFilePath' in study_dict else None
        return (study_id, file_path, md5, assembly, readme, entryUUID, raw_file_path)

    

    def remove_payload_directory(self):
        fh.remove_payload(self.callback_id)

    def clear_validated_files(self):
        fh.remove_payload_validated_files(self.callback_id)

    
    def update_publication_details(self, publication_content):
        author_name, pmid, gcst_list = self.parse_publication_content(publication_content)
        # removing constaint below as unpublished works won't have these.
        # may move to gcst only.
        #if not author_name:
        #    raise BadUserRequest("authorName not provided")
        #if not pmid:
        #    raise BadUserRequest("pmid not provided")
        if not gcst_list:
            raise BadUserRequest("studyList not provided")

        for i in gcst_list:
            if i["id"] not in [study.study_id for study in self.study_obj_list]:
                raise BadUserRequest("study id not found: {}".format(i["id"]))
            for study in self.study_obj_list:
                if str(study.study_id) == str(i["id"]):
                    study.set_author_name(author_name)
                    study.set_pmid(pmid)
                    study.set_gcst(i["gcst"])
                    study.store_publication_details()
                    break

    @staticmethod
    def parse_publication_content(publication_content):
        """
        Expecting:
        {
            "pmid": "1234567",
            "authorName": "BlogsJ",
            "studyList": [
                {
                    "id": "xyz321",
                    "gcst": "GCST_123456"
                },
                {
                    "id": "abc123",
                    "gcst": "GCST_2345667"
                }
            ]
        }
        """
        author_name = publication_content['authorName'] if 'authorName' in publication_content else None
        pmid = publication_content['pmid'] if 'pmid' in publication_content else None
        gcst_list = publication_content['studyList'] if 'studyList' in publication_content else None
        return (author_name, pmid, gcst_list)

    def clean_up_after_validation(self, ftp_server, ftp_user, ftp_password):
        ftp = fh.connect_to_ftp(server=ftp_server, user=ftp_user, password=ftp_password)
        for study in self.study_obj_list:
            study.clean_study_files_after_validation(ftp=ftp)
        ftp.quit()


def parse_payload(content, studyid, callback_id):
    payload = Payload(callback_id=callback_id, payload=content)
    payload.create_study_obj_list()
    payload.set_callback_id_for_studies()
    study_meta = [s for s in payload.study_obj_list if s.study_id == studyid]
    if len(study_meta) != 1:
        print("could not find only one matching study id in payload")
        return False
    return (
    study_meta[0].file_path, study_meta[0].md5, study_meta[0].assembly, study_meta[0].readme, study_meta[0].entryUUID)


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("-cid", help='The callback ID', required=True)
    argparser.add_argument("-payload", help='JSON payload (input)', required=True)
    argparser.add_argument("-storepath", help='The storage path you want the data written to e.g. /path/to/data',
                           required=False, default=config.STORAGE_PATH)
    argparser.add_argument("-validated_path",
                           help='The path you want the validated files written to e.g. /path/to/data', required=False,
                           default=config.VALIDATED_PATH)
    argparser.add_argument("-ftpserver", help='The FTP server name where your files are', required=False,
                           default=config.FTP_SERVER)
    argparser.add_argument("-ftpuser", help='The FTP username', required=False, default=config.FTP_USERNAME)
    argparser.add_argument("-ftppass", help='The FTP password', required=False, default=config.FTP_PASSWORD)

    args = argparser.parse_args()
    if args.storepath:
        config.STORAGE_PATH = args.storepath
    if args.validated_path:
        config.VALIDATED_PATH = args.validated_path
    if args.ftpserver:
        config.FTP_SERVER = args.ftpserver
    if args.ftpuser:
        config.FTP_USERNAME = args.ftpuser
    if args.ftppass:
        config.FTP_PASSWORD = args.ftppass

    if utils.is_path(args.payload):
        with open(args.payload, "r") as f:
            content = json.load(f)
    else:
        # if content is given as json string
        content = json.loads(args.payload)

    payload = Payload(callback_id=args.cid, payload=content)
    payload.create_study_obj_list()
    payload.set_callback_id_for_studies()
    payload.clean_up_after_validation(ftp_server=config.FTP_SERVER,
                                      ftp_user=config.FTP_USERNAME,
                                      ftp_password=config.FTP_PASSWORD)


if __name__ == '__main__':
    main()
