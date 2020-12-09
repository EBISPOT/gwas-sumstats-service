import unittest
import os
import json
import config
from tests.test_constants import *
import sumstats_service.resources.api_utils as au
from sumstats_service.resources.error_classes import *
from sumstats_service.resources.sqlite_client import sqlClient
from pymongo import MongoClient


class TestAPIUtils(unittest.TestCase):
    def setUp(self):
        self.testDB = "./tests/study_meta.db"
        self.test_storepath = "./tests/data"
        config.STORAGE_PATH = self.test_storepath
        config.DB_PATH = self.testDB
        sq = sqlClient(self.testDB)
        sq.create_conn()
        sq.cur.executescript(config.DB_SCHEMA)
        self.valid_url = "file://{}".format(os.path.abspath("./tests/test_sumstats_file.tsv"))
            

    def tearDown(self):
        os.remove(self.testDB)
        client = MongoClient(config.MONGO_URI)
        client.drop_database(config.MONGO_DB)

    def test_json_payload_to_db(self):
        result = au.json_payload_to_db(VALID_POST)
        self.assertIsNotNone(result)


    def test_delete_payload_from_db(self):
        valid_json = {
               "requestEntries": [
                   {
                    "id": "abc123",
                    "filePath": self.valid_url,
                    "md5":"a1195761f082f8cbc2f5a560743077cc",
                    "assembly":"GRCh38"
                   },
                   {
                    "id": "xyz321",
                    "filePath": self.valid_url,
                    "md5":"a1195761f082f8cbc2f5a560743077cc",
                    "assembly":"GRCh38"
                   },
                 ]
               } 
        cid = au.json_payload_to_db(valid_json)
        resp = au.validate_files_from_payload(cid, valid_json, minrows=10)
        au.store_validation_results_in_db(resp)
        path = os.path.join(self.test_storepath, cid)
        self.assertTrue(os.path.exists(path))
        resp = au.delete_payload_from_db(cid)
        check = json.loads(resp)
        self.assertEqual(check["callbackID"], cid)
        print(resp)
        au.remove_payload_files(cid)
        self.assertFalse(os.path.exists(path))


if __name__ == '__main__':
    unittest.main()
