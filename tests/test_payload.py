import unittest
import os
import config
from tests.test_constants import *
import resources.payload as pl
from resources.error_classes import *
from resources.sqlite_client import sqlClient


class TestAPIUtils(unittest.TestCase):
    def setUp(self):
        self.testDB = "./tests/study_meta.db"
        config.DB_PATH = self.testDB 
        sq = sqlClient(self.testDB)
        sq.create_conn()
        sq.cur.execute(config.DB_SCHEMA)


    def tearDown(self):
        os.remove(self.testDB)

    def test_generate_callback_id(self):
        payload = pl.Payload()
        payload.generate_callback_id()
        self.assertIsNotNone(payload.callback_id)

    def test_parse_new_study_json(self):
        data = {
                 "id": "xyz321",
                 "pmid": "1233454",
                 "filePath": "file/path.tsv",
                 "md5":"b1d7e0a58d36502d59d036a17336ddf5",
                 "assembly":"38"
                }
        payload = pl.Payload(data)
        result = payload.parse_new_study_json(data)
        self.assertEqual("xyz321", result[0])
        self.assertEqual("1233454", result[1])
        self.assertEqual("file/path.tsv", result[2])
        self.assertEqual("b1d7e0a58d36502d59d036a17336ddf5", result[3])
        self.assertEqual("38", result[4])

    def test_parse_new_study_bad_json(self):
        data_missing_field = {
                 "id": "xyz321",
                 "filePath": "file/path.tsv",
                 "md5":"b1d7e0a58d36502d59d036a17336ddf5",
                 "assembly":"38"
                }
        payload = pl.Payload(data_missing_field)        
        self.assertRaises(BadUserRequest, payload.parse_new_study_json, data_missing_field)

    def test_check_basic_content_present(self):
        data = {'requestEntries': [{}]}
        payload = pl.Payload(data)        
        self.assertTrue(payload.check_basic_content_present)
        missing_data = {'requestEntries': []}
        payload = pl.Payload(missing_data)        
        self.assertRaises(BadUserRequest, payload.check_basic_content_present)
        missing_all = {}
        payload = pl.Payload(missing_all)        
        self.assertRaises(BadUserRequest, payload.check_basic_content_present)

    def test_check_study_ids_ok(self):
        payload = pl.Payload(VALID_POST)
        self.assertTrue(payload.check_study_ids_ok())
        dupe_study = { 
                        "requestEntries": [
                            {
                             "id": "abc123",
                             "pmid": "1233454",
                             "filePath": "file/path.tsv",
                             "md5":"b1d7e0a58d36502d59d036a17336ddf5",
                             "assembly":"38"
                            },
                            {
                             "id": "abc123",
                             "pmid": "1233454",
                             "filePath": "file/path.tsv",
                             "md5":"b1d7e0a58d36502d59d036a17336ddf5",
                             "assembly":"38"
                            },
                          ]
                        }
        payload = pl.Payload(dupe_study)
        self.assertRaises(BadUserRequest, payload.check_study_ids_ok)

