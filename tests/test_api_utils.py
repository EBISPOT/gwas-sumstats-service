import json
import os
import unittest

from pymongo import MongoClient

import sumstats_service.resources.api_utils as au
from sumstats_service import config
from tests.test_constants import VALID_POST


class TestAPIUtils(unittest.TestCase):
    def setUp(self):
        self.test_storepath = os.path.abspath("./tests/data")
        config.STORAGE_PATH = os.path.abspath(self.test_storepath)
        config.DEPO_PATH = os.path.abspath("./tests")
        config.BROKER_PORT = 5682
        config.BROKER_HOST = "localhost"
        config.NEXTFLOW_CONFIG = "executor.name = 'local'\nexecutor.queueSize = 3"
        config.CONTAINERISE = False
        self.cid = "TiQS2yxV"
        self.sid = "mKoYvoLH8L"
        self.entryUUID = "ABC1234"
        self.valid_file = "test_sumstats_file.tsv"
        self.valid_content = {
            "requestEntries": [
                {
                    "id": self.sid,
                    "filePath": self.valid_file,
                    "md5": "a1195761f082f8cbc2f5a560743077cc",
                    "assembly": "GRCh38",
                    "entryUUID": self.entryUUID,
                },
            ]
        }

    def tearDown(self):
        mongo_uri = os.getenv("MONGO_URI", config.MONGO_URI)
        mongo_user = os.getenv("MONGO_USER", None)
        mongo_password = os.getenv("MONGO_PASSWORD", None)
        mongo_db = os.getenv("MONGO_DB", config.MONGO_DB)

        client = MongoClient(mongo_uri, username=mongo_user, password=mongo_password)
        client.drop_database(mongo_db)

    def test_json_payload_to_db(self):
        result = au.json_payload_to_db(VALID_POST)
        self.assertIsNotNone(result)

    def test_validate_files_from_payload(self):
        result_json = au.validate_files(
            callback_id=self.cid, content=self.valid_content, minrows=2
        )
        results = json.loads(result_json)
        self.assertEqual(results["validationList"][0]["id"], self.sid)

    def test_bypass_validation(self):
        result_json = au.skip_validation_completely(
            callback_id=self.cid, content=self.valid_content
        )
        results = json.loads(result_json)
        self.assertEqual(results["validationList"][0]["id"], self.sid)


if __name__ == "__main__":
    unittest.main()
