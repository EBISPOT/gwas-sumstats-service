from datetime import datetime
import logging

from pymongo import MongoClient as pymc

from sumstats_service import config

# Global MongoDB client instances
_mongo_client_instance = None
_flask_mongo_client_instance = None

logger = logging.getLogger(__name__)

def get_mongo_client(is_flask=False, **kwargs):
    """
    Get or create a MongoDB client based on context.
    
    Args:
        is_flask (bool): Whether this is being called from Flask context
        **kwargs: Additional parameters to pass to MongoClient
        
    Returns:
        MongoClient: A configured MongoDB client
    """
    global _mongo_client_instance, _flask_mongo_client_instance
    
    if is_flask:
        if _flask_mongo_client_instance is None:
            logger.info("Creating new Flask MongoDB client")
            _flask_mongo_client_instance = MongoClient(
                config.MONGO_URI,
                config.MONGO_USER,
                config.MONGO_PASSWORD,
                config.MONGO_DB,
                maxPoolSize=50,  
                minPoolSize=10,
                maxIdleTimeMS=120000,
                waitQueueTimeoutMS=10000,
                **kwargs
            )
        return _flask_mongo_client_instance
    else:
        if _mongo_client_instance is None:
            logger.info("Creating new worker MongoDB client")
            _mongo_client_instance = MongoClient(
                config.MONGO_URI,
                config.MONGO_USER,
                config.MONGO_PASSWORD,
                config.MONGO_DB,
                maxPoolSize=100,
                minPoolSize=20,
                maxIdleTimeMS=120000,
                waitQueueTimeoutMS=15000,
                **kwargs
            )
        return _mongo_client_instance


class MongoClient:
    def __init__(self, uri, username, password, database, **kwargs):
        """
        Initialize a MongoDB client.
        
        Args:
            uri (str): MongoDB connection URI
            username (str): MongoDB username
            password (str): MongoDB password
            database (str): Database name to connect to
            **kwargs: Additional connection parameters for pymongo
        """
        self.uri = uri
        self.username = username
        self.password = password
        
        # Create PyMongo client with connection pooling settings
        connection_params = {
            'username': self.username,
            'password': self.password
        }
        
        # Add any additional connection parameters
        connection_params.update(kwargs)
        
        self.client = pymc(self.uri, **connection_params)
        self.database = self.client[database]
        
        # Initialize collections
        self.study_collection = self.database["sumstats-study-meta"]
        self.error_collection = self.database["sumstats-errors"]
        self.callback_collection = self.database["sumstats-callback-tracking"]
        # TODO: This collection can be deleted after yaml gen fix
        self.task_failure_collection = self.database["sumstats-celery-task-failures"]
        self.metadata_yaml_collection = self.database["sumstats-metadata-yaml"]
        self.studies_collection = self.database["studies"]
        self.payload_collection = self.database["sumstats-validation-payload"]

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
        self,
        gcst_id,
        status,
        is_harmonised=False,
        additional_info=None,
        globus_endpoint_id=None,
    ):

        if additional_info is None:
            additional_info = {}

        logger.info(f"Adding {gcst_id} with hm: {is_harmonised} to yaml")

        update_doc = {
            "$set": {
                "request_updated": datetime.now(),
                "status": status.value,
                "additional_info": additional_info,
            },
            "$setOnInsert": {
                "request_created": datetime.now(),
                "globus_endpoint_id": globus_endpoint_id,
            },
        }

        # If status is COMPLETED, SKIPPED or PENDING, then reset attempts to 0.
        # Otherwise increment attempts.
        if status in [
            config.MetadataYamlStatus.COMPLETED,
            config.MetadataYamlStatus.SKIPPED,
            config.MetadataYamlStatus.PENDING,
        ]:
            update_doc["$set"]["attempts"] = 0
        else:
            update_doc["$inc"] = {"attempts": 1}

        # Perform the update
        self.metadata_yaml_collection.update_one(
            {
                "gcst_id": gcst_id,
                "is_harmonised": is_harmonised,
            },
            update_doc,
            upsert=True,
        )
        logger.info(f"Metadata YAML request for {gcst_id} inserted or updated.")

    def get_globus_endpoint_id(self, gcst_id):
        """
        Retrieve the globus_endpoint_id for a given gcst_id.

        Args:
            gcst_id (str): The GCST identifier.

        Returns:
            str or None: The globus_endpoint_id if found, otherwise None.
        """
        result = self.metadata_yaml_collection.find_one(
            {"gcst_id": gcst_id}, {"globus_endpoint_id": 1}
        )

        if result and "globus_endpoint_id" in result:
            return result["globus_endpoint_id"]

        logger.info(f"No globus_endpoint_id found for gcst_id: {gcst_id}")
        return None

    def upsert_payload(self, callback_id, payload=None, status=None):
        set_op = {"request_updated": datetime.now()}

        if payload is not None:
            set_op["payload"] = payload

        if status is not None:
            set_op["status"] = status.value

        self.payload_collection.update_one(
            {"callback_id": callback_id},
            {
                "$set": set_op,
                "$setOnInsert": {
                    "request_created": datetime.now(),
                    "callback_id": callback_id,
                },
            },
            upsert=True,
        )
        logger.info(f"Payload for callback_id='{callback_id}' upserted.")

    def get_payload(self, callback_id):
        _ = self.payload_collection.find_one({"callback_id": callback_id})
        return _["payload"]