import unittest
import os
import json
from sumstats_service import config
from tests.test_constants import *
import sumstats_service.resources.api_utils as au
from sumstats_service.resources.sqlite_client import sqlClient
from pymongo import MongoClient


class TestAPIUtils(unittest.TestCase):
    def setUp(self):
        self.testDB = "./tests/study_meta.db"
        self.test_storepath = os.path.abspath("./tests/data")
        config.STORAGE_PATH = self.test_storepath
        config.DB_PATH = self.testDB
        config.DEPO_PATH = os.path.abspath('./tests')
        config.BROKER_PORT = 5682
        config.BROKER_HOST = "localhost"
        config.NEXTFLOW_CONFIG = "executor.name = 'local'\nexecutor.queueSize = 3"
        sq = sqlClient(self.testDB)
        sq.create_conn()
        sq.cur.executescript(config.DB_SCHEMA)
        self.cid = "TiQS2yxV"
        self.sid = "mKoYvoLH8L"
        self.entryUUID = "ABC1234"
        self.valid_file = "test_sumstats_file.tsv"
        self.valid_content = {
                        "requestEntries": [
                          {
                            "id": self.sid,
                            "filePath": self.valid_file,
                            "md5":"a1195761f082f8cbc2f5a560743077cc",
                            "assembly":"GRCh38",
                            "entryUUID":self.entryUUID
                           },
                         ]
                       }
            

    def tearDown(self):
        os.remove(self.testDB)
        client = MongoClient(config.MONGO_URI)
        client.drop_database(config.MONGO_DB)

    def test_json_payload_to_db(self):
        result = au.json_payload_to_db(VALID_POST)
        self.assertIsNotNone(result)

    def test_validate_files_from_payload(self):
        result_json = au.validate_files(callback_id=self.cid,
                                    content=self.valid_content,
                                    minrows=2)
        results = json.loads(result_json)
        self.assertEqual(results['validationList'][0]["id"], self.sid)





if __name__ == '__main__':
    unittest.main()
