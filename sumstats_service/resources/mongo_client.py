from datetime import datetime

from pymongo import MongoClient as pymc

from sumstats_service import config


class MongoClient:
    def __init__(self, uri, username, password, database):
        self.uri = uri
        self.username = username
        self.password = password
        self.client = pymc(self.uri, username=self.username, password=self.password)
        self.database = self.client[database]
        self.study_collection = self.database["sumstats-study-meta"]
        self.error_collection = self.database["sumstats-errors"]
        self.callback_collection = self.database["sumstats-callback-tracking"]
        # TODO: update cron entries and delete this collection
        self.task_failure_collection = self.database["sumstats-celery-task-failures"]
        self.metadata_yaml_collection = self.database["sumstats-metadata-yaml"]
        self.studies_collection = self.database["studies"]

    """ generic methods"""

    def find_one(self, collection):
        return collection.find_one({}, {"_id": 0})

    def replace_one(self, collection, objectid, data):
        return collection.replace_one({"_id": objectid}, data)

    def insert(self, collection, data):
        return collection.insert_one(data)

    ######################
    # Specific Methods
    ######################

    def insert_new_study(self, data):
        fields = [
            "studyID",
            "callbackID",
            "filePath",
            "md5",
            "assembly",
            "readme",
            "entryUUID",
            "rawSS",
            "fileType",
        ]
        study_data_dict = dict(zip(fields, data))
        self.insert(self.study_collection, study_data_dict)

    def get_study_metadata(self, study):
        meta_dict = self.study_collection.find_one({"studyID": study})
        return meta_dict

    def get_study_metadata_by_gcst(self, gcst):
        # meta_dict = self.study_collection.find_one({"gcst": gcst})
        # Note that we use .find() rather than .find_one() as above. The reason
        # is that there might exist multiple entries for a single gcst id, e.g.,
        # when the template is edited. Therefore, here, we first get all, then
        # sort by _id descending, get the last one (which should be the latest entry).
        last_created_entry = (
            self.study_collection.find({"gcst": gcst}).sort("_id", -1).limit(1)
        )
        meta_dict = next(last_created_entry, None)
        return meta_dict

    def update_retrieved_status(self, study, status):
        data = self.get_study_metadata(study)
        objectid = data["_id"]
        data["retrieved"] = status
        self.replace_one(self.study_collection, objectid, data)

    def update_data_valid_status(self, study, status):
        data = self.get_study_metadata(study)
        objectid = data["_id"]
        data["dataValid"] = status
        self.replace_one(self.study_collection, objectid, data)

    def update_error_code(self, study, error_code):
        data = self.get_study_metadata(study)
        objectid = data["_id"]
        data["errorCode"] = error_code
        self.replace_one(self.study_collection, objectid, data)

    def update_publication_details(self, study, author_name, pmid, gcst):
        data = self.get_study_metadata(study)
        objectid = data["_id"]
        data["authorName"] = author_name
        data["pmid"] = pmid
        data["gcst"] = gcst
        self.replace_one(self.study_collection, objectid, data)

    def get_study_count(self):
        return self.study_collection.count_documents({})

    def check_callback_id_in_db(self, callback_id):
        studies = [i for i in self.study_collection.find({"callbackID": callback_id})]
        if not len(studies):
            # check it hasn't been registered but not yet added to the studies db
            callback_registered = [
                i for i in self.callback_collection.find({"callbackID": callback_id})
            ]
            if not len(callback_registered):
                return False
        return True

    def register_callback_id(self, callback_id):
        self.insert(self.callback_collection, {"callbackID": callback_id})

    def remove_callback_id(self, callback_id):
        self.callback_collection.delete_many({"callbackID": callback_id})

    def update_metadata_errors(self, callback_id, error_list):
        data = self.callback_collection.find_one({"callbackID": callback_id})
        objectid = data["_id"]
        data["metadataErrors"] = error_list
        self.replace_one(self.callback_collection, objectid, data)

    def update_bypass_validation_status(
        self, callback_id: str, bypass_validation: bool
    ) -> None:
        data = self.callback_collection.find_one({"callbackID": callback_id})
        objectid = data["_id"]
        data["bypassValidation"] = bypass_validation
        self.replace_one(self.callback_collection, objectid, data)

    def get_bypass_validation_status(self, callback_id: str) -> bool:
        data = self.callback_collection.find_one({"callbackID": callback_id})
        if data and "bypassValidation" in data:
            return data["bypassValidation"]
        return False

    def get_metadata_errors(self, callback_id):
        data = self.callback_collection.find_one({"callbackID": callback_id})
        if data and "metadataErrors" in data:
            return data["metadataErrors"]
        return []

    def get_data_from_callback_id(self, callback_id):
        studies = self.study_collection.find({"callbackID": callback_id})
        data = [s for s in studies]
        return data if data else None

    def get_error_message_from_code(self, code):
        if self.error_collection.count_documents({}) == 0:
            self.create_error_table()
        error_text = self.error_collection.find_one({"id": code})["errorText"]
        return error_text

    def create_error_table(self):
        for error in config.VALIDATION_ERRORS:
            self.insert(self.error_collection, error)

    def delete_study_entry(self, study):
        self.study_collection.delete_many({"studyID": study})

    def insert_task_failure(self, gcst_id, exception):
        self.insert(
            self.task_failure_collection,
            {
                "gcst_id": gcst_id,
                "exception": str(exception),
                "timestamp": datetime.now(),
            },
        )

    def get_study(self, gcst_id):
        return self.studies_collection.find_one({"accession": gcst_id})

    def insert_or_update_metadata_yaml_request(
        self, gcst_id, status, additional_info={}
    ):
        self.metadata_yaml_collection.update_one(
            {"gcst_id": gcst_id},
            {
                "$set": {
                    "request_updated": datetime.now(),
                    "status": status.value,
                    "additional_info": additional_info,
                },
                "$setOnInsert": {
                    "request_created": datetime.now(),
                },
            },
            upsert=True,
        )
        print(f"Metadata YAML request for {gcst_id} inserted or updated.")
