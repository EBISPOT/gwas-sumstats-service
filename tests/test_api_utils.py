import unittest
import os
import json
import config
from tests.test_constants import *
import sumstats_service.resources.api_utils as au
from sumstats_service.resources.error_classes import *
from sumstats_service.resources.sqlite_client import sqlClient
import requests
import requests_mock

class TestAPIUtils(unittest.TestCase):
    def setUp(self):
        self.testDB = "./tests/study_meta.db"
        self.test_storepath = "./tests/data"
        config.STORAGE_PATH = self.test_storepath
        config.DB_PATH = self.testDB
        sq = sqlClient(self.testDB)
        sq.create_conn()
        sq.cur.executescript(config.DB_SCHEMA)
        self.valid_url = "https://valid_file.tsv"
        with open("./tests/test_sumstats_file.tsv", "rb") as f:
            self.valid_content = f.read()
            

    def tearDown(self):
        os.remove(self.testDB)

    def test_json_payload_to_db(self):
        result = au.json_payload_to_db(VALID_POST)
        self.assertIsNotNone(result)

    @requests_mock.Mocker()
    def test_validate_good_files_from_payload(self, m):
        m.register_uri('GET', self.valid_url, content=self.valid_content)
        cid = au.json_payload_to_db(VALID_POST)
        resp = au.validate_files_from_payload(cid, VALID_POST)
        check = json.loads(resp)
        self.assertEqual(check["callbackID"], cid)
        self.assertEqual(check["validationList"][0]["retrieved"], 1)
        self.assertEqual(check["validationList"][0]["dataValid"], 1)
        self.assertIsNone(check["validationList"][0]["errorCode"])

    @requests_mock.Mocker()
    def test_validate_bad_URL_files_from_payload(self, m):
        one_bad_md5 = {
               "requestEntries": [
                   {
                    "id": "abc123",
                    "filePath": "https://does_not_exist.tsv",
                    "md5":"a1195761f082f8cbc2f5a560743077cc",
                    "assembly":"38"
                   },
                   {
                    "id": "xyz321",
                    "filePath": "https://valid_file.tsv",
                    "md5":"a1195761f082f8cbc2f5a560743077cc",
                    "assembly":"38"
                   },
                 ]
               }
        m.register_uri('GET', self.valid_url, content=self.valid_content)
        m.register_uri('GET', "https://does_not_exist.tsv", status_code=404)
        cid = au.json_payload_to_db(one_bad_md5)
        resp = au.validate_files_from_payload(cid, one_bad_md5)
        check = json.loads(resp)
        self.assertEqual(check["callbackID"], cid)
        self.assertEqual(check["validationList"][0]["retrieved"], 0)
        self.assertIsNone(check["validationList"][0]["dataValid"])
        self.assertEqual(check["validationList"][0]["errorCode"], 1)
        self.assertEqual(check["validationList"][1]["retrieved"], 1)
        self.assertEqual(check["validationList"][1]["dataValid"], 1)
        self.assertIsNone(check["validationList"][1]["errorCode"])

    @requests_mock.Mocker()
    def test_validate_bad_md5_files_from_payload(self, m):
        one_bad_md5 = {
               "requestEntries": [
                   {
                    "id": "abc123",
                    "filePath": "https://valid_file.tsv",
                    "md5":"a1195761f082f8cbc2f5a560743077cc",
                    "assembly":"38"
                   },
                   {
                    "id": "xyz321",
                    "filePath": "https://valid_file.tsv",
                    "md5":"a1195761f082f8cbc2f5a560743077BAD",
                    "assembly":"38"
                   },
                 ]
               }
        m.register_uri('GET', self.valid_url, content=self.valid_content)
        cid = au.json_payload_to_db(one_bad_md5)
        resp = au.validate_files_from_payload(cid, one_bad_md5)
        check = json.loads(resp)
        self.assertEqual(check["callbackID"], cid)
        self.assertEqual(check["validationList"][0]["retrieved"], 1)
        self.assertEqual(check["validationList"][0]["dataValid"], 1)
        self.assertIsNone(check["validationList"][0]["errorCode"])
        self.assertEqual(check["validationList"][1]["retrieved"], 1)
        self.assertEqual(check["validationList"][1]["dataValid"], 0)
        self.assertEqual(check["validationList"][1]["errorCode"], 2)

        

if __name__ == '__main__':
    unittest.main()
