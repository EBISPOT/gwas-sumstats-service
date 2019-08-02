import unittest
import os
import config
from tests.test_constants import *
import sumstats_service.resources.payload as pl
from sumstats_service.resources.error_classes import *
from sumstats_service.resources.sqlite_client import sqlClient


class TestPayload(unittest.TestCase):
    def setUp(self):
        self.testDB = "./tests/study_meta.db"
        self.test_storepath = "./tests/data"
        config.STORAGE_PATH = self.test_storepath
        config.DB_PATH = self.testDB
        sq = sqlClient(self.testDB)
        sq.create_conn()
        sq.cur.executescript(config.DB_SCHEMA)


    def tearDown(self):
        os.remove(self.testDB)

    def test_generate_callback_id(self):
        payload = pl.Payload()
        payload.generate_callback_id()
        self.assertIsNotNone(payload.callback_id)

    def test_parse_new_study_json(self):
        data = {
                 "id": "xyz321",
                 "filePath": "file/path.tsv",
                 "md5":"b1d7e0a58d36502d59d036a17336ddf5",
                 "assembly":"38"
                }
        payload = pl.Payload(payload=data)
        result = payload.parse_new_study_json(data)
        self.assertEqual("xyz321", result[0])
        self.assertEqual("file/path.tsv", result[1])
        self.assertEqual("b1d7e0a58d36502d59d036a17336ddf5", result[2])
        self.assertEqual("38", result[3])

    def test_parse_new_study_bad_json(self):
        data_missing_field = {
                 "id": "xyz321",
                 "md5":"b1d7e0a58d36502d59d036a17336ddf5",
                 "assembly":"38"
                }
        payload = pl.Payload(payload=data_missing_field)
        self.assertRaises(BadUserRequest, payload.parse_new_study_json, data_missing_field)

    def test_check_basic_content_present(self):
        data = {'requestEntries': [{}]}
        payload = pl.Payload(payload=data)
        self.assertTrue(payload.check_basic_content_present)
        missing_data = {'requestEntries': []}
        payload = pl.Payload(payload=missing_data)
        self.assertRaises(BadUserRequest, payload.check_basic_content_present)
        missing_all = {}
        payload = pl.Payload(payload=missing_all)
        self.assertRaises(BadUserRequest, payload.check_basic_content_present)

    def test_create_study_obj_list(self):
        payload = pl.Payload(payload=VALID_POST)
        self.assertTrue(payload.create_study_obj_list())
        dupe_study = {
                        "requestEntries": [
                            {
                             "id": "abc123",
                             "filePath": "file/path.tsv",
                             "md5":"b1d7e0a58d36502d59d036a17336ddf5",
                             "assembly":"38"
                            },
                            {
                             "id": "abc123",
                             "filePath": "file/path.tsv",
                             "md5":"b1d7e0a58d36502d59d036a17336ddf5",
                             "assembly":"38"
                            },
                          ]
                        }
        payload = pl.Payload(payload=dupe_study)
        self.assertRaises(BadUserRequest, payload.create_study_obj_list)

    def test_get_data_for_callback_id(self):
        payload = pl.Payload(payload=VALID_POST)
        payload.payload_to_db()
        cid = payload.callback_id
        payload_new = pl.Payload(callback_id=cid)
        for study in payload_new.study_obj_list:
            self.assertEqual(study.callback_id, cid)


    def test_get_payload_complete_status(self):
        payload = pl.Payload(payload=VALID_POST)
        payload.payload_to_db()
        cid = payload.callback_id
        completed = payload.get_payload_complete_status()
        self.assertEqual(completed, False)
        for study in payload.study_obj_list:
            study.update_retrieved_status(1)
            study.update_data_valid_status(1)
        payload_new = pl.Payload(callback_id=cid)
        completed = payload_new.get_payload_complete_status()
        self.assertEqual(completed, True)


