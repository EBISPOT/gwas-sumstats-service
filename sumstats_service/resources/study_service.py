import re

import sumstats_service.resources.file_handler as fh
from sumstats_service import config
from sumstats_service.resources.error_classes import *
from sumstats_service.resources.mongo_client import MongoClient


class Study:
    def __init__(
        self,
        study_id,
        file_path=None,
        md5=None,
        assembly=None,
        callback_id=None,
        retrieved=None,
        data_valid=None,
        status=None,
        error_code=None,
        readme=None,
        entryUUID=None,
        author_name=None,
        pmid=None,
        gcst=None,
        raw_ss=None,
        file_type=None,
    ):
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
        self.raw_ss = raw_ss
        self.file_type = file_type

    def valid_study_id(self):
        if re.match("^[a-zA-Z0-9]+$", self.study_id) and len(self.study_id) > 3:
            return True
        return False

    def get_status(self):
        if self.error_code is not None:
            status = "INVALID"
        elif self.retrieved is None and self.data_valid is None:
            status = "RETRIEVING"
        elif self.retrieved == 1 and self.data_valid is None:
            status = "VALIDATING"
        elif self.retrieved == 0 or self.data_valid == 0:
            status = "INVALID"
        elif self.retrieved == 1 and self.data_valid == 1:
            status = "VALID"
        elif self.retrieved == 99 and self.data_valid == 99:
            status = "IGNORE"
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
        mdb = MongoClient(
            config.MONGO_URI, config.MONGO_USER, config.MONGO_PASSWORD, config.MONGO_DB
        )
        mdb.delete_study_entry(self.study_id)

    def store_validation_statuses(self):
        self.store_retrieved_status()
        self.store_data_valid_status()
        self.store_error_code()

    def store_retrieved_status(self):
        mdb = MongoClient(
            config.MONGO_URI, config.MONGO_USER, config.MONGO_PASSWORD, config.MONGO_DB
        )
        mdb.update_retrieved_status(self.study_id, self.retrieved)

    def store_data_valid_status(self):
        mdb = MongoClient(
            config.MONGO_URI, config.MONGO_USER, config.MONGO_PASSWORD, config.MONGO_DB
        )
        mdb.update_data_valid_status(self.study_id, self.data_valid)

    def store_error_code(self):
        # error codes are in the error table (see the DB_SCHEMA)
        mdb = MongoClient(
            config.MONGO_URI, config.MONGO_USER, config.MONGO_PASSWORD, config.MONGO_DB
        )
        mdb.update_error_code(self.study_id, self.error_code)

    def store_publication_details(self):
        mdb = MongoClient(
            config.MONGO_URI, config.MONGO_USER, config.MONGO_PASSWORD, config.MONGO_DB
        )
        mdb.update_publication_details(
            self.study_id, self.author_name, self.pmid, self.gcst
        )

    def valid_md5(self):
        # check is alphanumeric
        return self.md5.isalnum()

    def study_id_exists_in_db(self):
        if self.get_study_from_db():
            return True
        return False

    def get_study_from_db(self):
        mdb = MongoClient(
            config.MONGO_URI,
            config.MONGO_USER,
            config.MONGO_PASSWORD,
            config.MONGO_DB,
        )
        study_metadata = mdb.get_study_metadata(self.study_id)

        if study_metadata:
            self.study_id = set_var_from_dict(study_metadata, "studyID", None)
            self.callback_id = set_var_from_dict(study_metadata, "callbackID", None)
            self.file_path = set_var_from_dict(study_metadata, "filePath", None)
            self.md5 = set_var_from_dict(study_metadata, "md5", None)
            self.assembly = set_var_from_dict(study_metadata, "assembly", None)
            self.retrieved = set_var_from_dict(study_metadata, "retrieved", None)
            self.data_valid = set_var_from_dict(study_metadata, "dataValid", None)
            self.error_code = set_var_from_dict(study_metadata, "errorCode", None)
            self.readme = set_var_from_dict(study_metadata, "readme", None)
            self.entryUUID = set_var_from_dict(study_metadata, "entryUUID", None)
            self.author_name = set_var_from_dict(study_metadata, "authorName", None)
            self.pmid = set_var_from_dict(study_metadata, "pmid", None)
            self.gcst = set_var_from_dict(study_metadata, "gcst", None)
            self.raw_ss = set_var_from_dict(study_metadata, "rawSS", None)
            self.file_type = set_var_from_dict(study_metadata, "fileType", None)
            self.set_error_text()
        return study_metadata

    def set_error_text(self):
        mdb = MongoClient(
            config.MONGO_URI, config.MONGO_USER, config.MONGO_PASSWORD, config.MONGO_DB
        )

        if self.error_code:
            self.error_text = mdb.get_error_message_from_code(self.error_code)
            # We may want a catch if the code is not seen in the database
        else:
            self.error_text = None

    def create_entry_for_study(self):
        # Order here matters
        data = [
            self.study_id,
            self.callback_id,
            self.file_path,
            self.md5,
            self.assembly,
            self.readme,
            self.entryUUID,
            self.raw_ss,
            self.file_type,
        ]
        mdb = MongoClient(
            config.MONGO_URI,
            config.MONGO_USER,
            config.MONGO_PASSWORD,
            config.MONGO_DB,
        )
        mdb.insert_new_study(data)

    def valid_assembly(self):
        if self.assembly not in config.VALID_ASSEMBLIES:
            return False
        else:
            return True

    def mandatory_metadata_check(self):
        mandatory_fields = [self.study_id, self.file_path, self.md5, self.assembly]
        if None in mandatory_fields or "" in mandatory_fields:
            self.set_error_code(4)
            return False
        else:
            if not self.valid_assembly():
                self.set_error_code(5)
            return True

    def retrieve_study_file(self):
        ssf = fh.SumStatFile(
            file_path=self.file_path,
            callback_id=self.callback_id,
            study_id=self.study_id,
            entryUUID=self.entryUUID,
        )
        retrieved = ssf.retrieve()
        if retrieved:
            self.set_retrieved_status(1)
            return True
        else:
            self.set_retrieved_status(0)
            self.set_error_code(1)
            return False

    def validate_study(self, minrows=None, forcevalid=False, zero_p_values=False):
        # Step through the validation
        if self.mandatory_metadata_check() is True:
            ssf = fh.SumStatFile(
                file_path=self.file_path,
                callback_id=self.callback_id,
                study_id=self.study_id,
                md5exp=self.md5,
                readme=self.readme,
                entryUUID=self.entryUUID,
                minrows=minrows,
                raw_ss=self.raw_ss,
                genome_assembly=self.assembly,
                zero_p_values=zero_p_values,
            )
            if not ssf.md5_ok():
                self.set_data_valid_status(0)
                self.set_error_code(2)
                # retrieved must be true
                self.set_retrieved_status(1)
            else:
                # retrieved must be true
                self.set_retrieved_status(1)
                if ssf.check_raw_ss():
                    validation_status = (
                        ssf.validate_file() if forcevalid is False else True
                    )
                    if validation_status is True:
                        self.set_data_valid_status(1)
                        # ssf.write_readme_file()
                        # ssf.tidy_files()
                    else:
                        self.set_data_valid_status(0)
                        self.set_error_code(ssf.validation_error)
                else:
                    self.set_data_valid_status(0)
                    self.set_error_code(11)

    def move_file_to_staging(self):
        dir_name = self.gcst
        sumstats_file_name = self.gcst
        ssf = fh.SumStatFile(
            file_path=self.file_path,
            callback_id=self.callback_id,
            study_id=self.study_id,
            readme=self.readme,
            entryUUID=self.entryUUID,
            staging_dir_name=dir_name,
            staging_file_name=sumstats_file_name,
            md5exp=self.md5,
            raw_ss=self.raw_ss,
        )
        return ssf.move_file_to_staging()


def set_var_from_dict(dictionary, var_name, default):
    return dictionary[var_name] if var_name in dictionary else default
