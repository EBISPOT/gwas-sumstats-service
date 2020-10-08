from pymongo import MongoClient
from bson.objectid import ObjectId
import config


class mongoClient():
    def __init__(self, uri, username, password, database):
        self.uri = uri
        self.username = username
        self.password = password
        self.client = MongoClient(self.uri, username=self.username, password=self.password)
        self.database = self.client[database]
        self.study_collection = self.database['sumstats-study-meta']
        self.error_collection = self.database['sumstats-errors']

    """ generic methods"""

    def find_one(self, collection):
        return collection.find_one({}, { '_id': 0 })

    def replace_one(self, collection, objectid, data):
        return collection.replace_one({'_id': objectid}, data)

    def insert(self, collection, data):
        return collection.insert(data, check_keys=False)

    """ specific methods """
 
    def insert_new_study(self, data):
        fields = ["studyID", 
                  "callbackID", 
                  "filePath", 
                  "md5", 
                  "assembly", 
                  "readme", 
                  "entryUUID"]
        study_data_dict = dict(zip(fields, data))
        self.insert(self.study_collection, study_data_dict)
        # Can create index if needed

    def get_study_metadata(self, study):
        meta_dict = self.study_collection.find_one({"studyID": study})
        return meta_dict
        
    def update_retrieved_status(self, study, status):
        data = self.get_study_metadata(study)
        objectid = data['_id']
        data['retrieved'] = status
        self.replace_one(self.study_collection, objectid, data)

    def update_data_valid_status(self, study, status):
        data = self.get_study_metadata(study)
        objectid = data['_id']
        data['dataValid'] = status
        self.replace_one(self.study_collection, objectid, data)

    def update_error_code(self, study, error_code):
        data = self.get_study_metadata(study)
        objectid = data['_id']
        data['errorCode'] = error_code
        self.replace_one(self.study_collection, objectid, data)

    def update_publication_details(self, study, author_name, pmid, gcst):
        data = self.get_study_metadata(study)
        objectid = data['_id']
        data['authorName'] = author_name
        data['pmid'] = pmid
        data['gcst'] = gcst
        self.replace_one(self.study_collection, objectid, data)

    def get_study_count(self):
        return self.study_collection.count_documents({})

    def get_data_from_callback_id(self, callback_id):
        studies = self.study_collection.find({"callbackID": callback_id})
        data = [s for s in studies]
        return data if data else None

    def get_error_message_from_code(self, code):
        if self.error_collection.count_documents({}) == 0:
            self.create_error_table()
        error_text = self.error_collection.find_one({"id": code})['errorText']
        return error_text

    def create_error_table(self):
        for error in config.VALIDATION_ERRORS:
            self.insert(self.error_collection, error)

    def delete_study_entry(self, study):
        self.study_collection.delete_many({'studyID': study})
        






