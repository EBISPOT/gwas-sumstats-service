import re
import config
from sumstats_service.resources.error_classes import *
#from sumstats_service.resources.sqlite_client import sqlClient
import sumstats_service.resources.file_handler as fh
from sumstats_service.resources.mongo_client import mongoClient


class Study:
    def __init__(self, study_id, file_path=None,
                 md5=None, assembly=None, callback_id=None,
                 retrieved=None, data_valid=None, status=None, 
                 error_code=None, readme=None, entryUUID=None,
                 author_name=None, pmid=None, gcst=None):
        self.study_id = study_id
        self.file_path = file_path
        self.md5 = md5
        self.assembly = assembly
        self.callback_id = callback_id
        self.retrieved = retrieved
        self.data_valid = data_valid
        self.error_code = error_code
        self.error_text = None
        self.readme = readme
        self.entryUUID = entryUUID
        self.author_name = author_name
        self.pmid = pmid
        self.gcst = gcst

    def valid_study_id(self):
        if re.match('^[a-zA-Z0-9]+$', self.study_id) and len(self.study_id) > 3:
            return True
        return False

    def get_status(self):
        if self.error_code is not None:
            status = 'INVALID'
        elif self.retrieved is None and self.data_valid is None:
           status = 'RETRIEVING'
        elif self.retrieved is 1 and self.data_valid is None:
            status = 'VALIDATING'
        elif self.retrieved is 0 or self.data_valid is 0:
            status = 'INVALID'
        elif self.retrieved is 1 and self.data_valid is 1:
            status = 'VALID'
        return status

    def get_error_report(self):
        self.set_error_text()
        return self.error_text

    def set_retrieved_status(self, status):
        self.retrieved = status

    def set_data_valid_status(self, status):
        self.data_valid = status

    def set_author_name(self, author_name):
        self.author_name = author_name

    def set_pmid(self, pmid):
        self.pmid = pmid

    def set_gcst(self, gcst):
        self.gcst = gcst

    def get_gcst(self):
        return self.gcst

    def set_error_code(self, error_code):
        # error codes are in the error table (see the DB_SCHEMA)
        self.error_code = error_code

    def remove(self):
        mdb = mongoClient(config.MONGO_URI, config.MONGO_USER, config.MONGO_PASSWORD, config.MONGO_DB)
        mdb.delete_study_entry(self.study_id)

    def store_validation_statuses(self):
        self.store_retrieved_status()
        self.store_data_valid_status()
        self.store_error_code()

    def store_retrieved_status(self):
        mdb = mongoClient(config.MONGO_URI, config.MONGO_USER, config.MONGO_PASSWORD, config.MONGO_DB)
        mdb.update_retrieved_status(self.study_id, self.retrieved)

    def store_data_valid_status(self):
        mdb = mongoClient(config.MONGO_URI, config.MONGO_USER, config.MONGO_PASSWORD, config.MONGO_DB)
        mdb.update_data_valid_status(self.study_id, self.data_valid)

    def store_error_code(self):
        # error codes are in the error table (see the DB_SCHEMA)
        mdb = mongoClient(config.MONGO_URI, config.MONGO_USER, config.MONGO_PASSWORD, config.MONGO_DB)
        mdb.update_error_code(self.study_id, self.error_code)

    def store_publication_details(self):
        mdb = mongoClient(config.MONGO_URI, config.MONGO_USER, config.MONGO_PASSWORD, config.MONGO_DB)
        mdb.update_publication_details(self.study_id, self.author_name, self.pmid, self.gcst)

    def valid_md5(self):
        # check is alphanumeric
        return self.md5.isalnum()

    def study_id_exists_in_db(self):
        if self.get_study_from_db():
            return True
        return False

    def get_study_from_db(self):
        #sq = sqlClient(config.DB_PATH)
        #study_metadata = sq.get_study_metadata(self.study_id)
        
        mdb = mongoClient(config.MONGO_URI, config.MONGO_USER, config.MONGO_PASSWORD, config.MONGO_DB)
        study_metadata = mdb.get_study_metadata(self.study_id)

        if study_metadata:
            self.study_id = set_var_from_dict(study_metadata, 'studyID', None)
            self.callback_id = set_var_from_dict(study_metadata, 'callbackID', None)
            self.file_path = set_var_from_dict(study_metadata, 'filePath', None)
            self.md5 = set_var_from_dict(study_metadata, 'md5', None)
            self.assembly = set_var_from_dict(study_metadata, 'assembly', None)
            self.retrieved = set_var_from_dict(study_metadata, 'retrieved', None) 
            self.data_valid = set_var_from_dict(study_metadata, 'dataValid', None)
            self.error_code = set_var_from_dict(study_metadata, 'errorCode', None)
            self.readme = set_var_from_dict(study_metadata, 'readme', None)
            self.entryUUID = set_var_from_dict(study_metadata, 'entryUUID', None)
            self.author_name = set_var_from_dict(study_metadata, 'authorName', None)
            self.pmid = set_var_from_dict(study_metadata, 'pmid', None)
            self.gcst = set_var_from_dict(study_metadata, 'gcst', None)
            self.set_error_text()
        return study_metadata

    def set_error_text(self):
        #sq = sqlClient(config.DB_PATH)        
        mdb = mongoClient(config.MONGO_URI, config.MONGO_USER, config.MONGO_PASSWORD, config.MONGO_DB)
        
        if self.error_code:
            self.error_text = mdb.get_error_message_from_code(self.error_code)
            # We may want a catch if the code is not seen in the database
        else:
            self.error_text = None

    def create_entry_for_study(self):
        # Order here matters
        data = [self.study_id,
                self.callback_id,
                self.file_path,
                self.md5,
                self.assembly,
                self.readme,
                self.entryUUID
                ]
        #sq = sqlClient(config.DB_PATH)
        #sq.insert_new_study(data)
        mdb = mongoClient(config.MONGO_URI, config.MONGO_USER, config.MONGO_PASSWORD, config.MONGO_DB)
        mdb.insert_new_study(data)


    def valid_assembly(self):
        if self.assembly not in config.VALID_ASSEMBLIES:
            return False
        else:
            return True


    def mandatory_metadata_check(self):
        mandatory_fields = [self.study_id, self.file_path, self.md5, self.assembly]
        if None in mandatory_fields or "" in mandatory_fields:
            return False
        else:
            return True


    def validate_study(self):
        # Step through the validation
        if not self.mandatory_metadata_check():
            self.set_error_code(4)
        else:
            if not self.valid_assembly():
                self.set_error_code(5)
            else:
                ssf = fh.SumStatFile(file_path=self.file_path, callback_id=self.callback_id, study_id=self.study_id, 
                        md5exp=self.md5, readme=self.readme, entryUUID=self.entryUUID)
                if ssf.retrieve() is True:
                    self.set_retrieved_status(1)
                    if not ssf.md5_ok():
                        self.set_data_valid_status(0)
                        self.set_error_code(2)
                    else:
                        if ssf.validate_file():
                            self.set_data_valid_status(1)
                            ssf.write_readme_file()
                        else:
                            self.set_data_valid_status(0)
                            self.set_error_code(3)
                else:
                    self.set_retrieved_status(0)
                    self.set_error_code(1)
    
    
    def move_file_to_staging(self):
        dirname = self.gcst
        if self.author_name and self.pmid:
            dir_name = '_'.join([self.author_name, str(self.pmid), self.gcst])
        sumstats_file_name = self.gcst + '_build' + str(self.assembly)
        ssf = fh.SumStatFile(file_path=self.file_path, callback_id=self.callback_id, 
                study_id=self.study_id, readme=self.readme, entryUUID=self.entryUUID, 
                staging_dir_name=dir_name, staging_file_name=sumstats_file_name)
        return ssf.move_file_to_staging()
    
    
def set_var_from_dict(dictionary, var_name, default):
    return dictionary[var_name] if var_name in dictionary else default
 
        
    
        
