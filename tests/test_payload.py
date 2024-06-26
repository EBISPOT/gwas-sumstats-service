import os
import unittest

from pymongo import MongoClient

import sumstats_service.resources.payload as pl
from sumstats_service import config
from tests.test_constants import VALID_POST


class TestPayload(unittest.TestCase):
    def setUp(self):
        self.test_storepath = "./tests/data"
        config.STORAGE_PATH = self.test_storepath
        config.BROKER_PORT = 5682
        config.BROKER_HOST = "localhost"

    def tearDown(self):
        mongo_uri = os.getenv("MONGO_URI", config.MONGO_URI)
        mongo_user = os.getenv("MONGO_USER", None)
        mongo_password = os.getenv("MONGO_PASSWORD", None)
        mongo_db = os.getenv("MONGO_DB", config.MONGO_DB)

        client = MongoClient(mongo_uri, username=mongo_user, password=mongo_password)
        client.drop_database(mongo_db)

    def test_generate_callback_id(self):
        payload = pl.Payload()
        payload.generate_callback_id()
        self.assertIsNotNone(payload.callback_id)

    def test_parse_new_study_json(self):
        data = {
            "id": "xyz321",
            "filePath": "file/path.tsv",
            "md5": "b1d7e0a58d36502d59d036a17336ddf5",
            "assembly": "GRCh38",
        }
        payload = pl.Payload(payload=data)
        result = payload.parse_new_study_json(data)
        self.assertEqual("xyz321", result[0])
        self.assertEqual("file/path.tsv", result[1])
        self.assertEqual("b1d7e0a58d36502d59d036a17336ddf5", result[2])
        self.assertEqual("GRCh38", result[3])

    def test_parse_new_study_bad_json(self):
        data_missing_field = {
            "id": "xyz321",
            "md5": "b1d7e0a58d36502d59d036a17336ddf5",
            "assembly": "GRCh38",
        }
        payload = pl.Payload(payload=data_missing_field)
        (
            study_id,
            file_path,
            md5,
            assembly,
            readme,
            entryUUID,
            rawSS,
        ) = payload.parse_new_study_json(data_missing_field)
        self.assertIsNone(file_path)

    def test_check_basic_content_present(self):
        data = {"requestEntries": [{}]}
        payload = pl.Payload(payload=data)
        self.assertTrue(payload.check_basic_content_present())
        missing_data = {"requestEntries": []}
        payload = pl.Payload(payload=missing_data)
        self.assertFalse(payload.check_basic_content_present())
        missing_all = {}
        payload = pl.Payload(payload=missing_all)
        self.assertFalse(payload.check_basic_content_present())

    def test_create_study_obj_list(self):
        payload = pl.Payload(payload=VALID_POST)
        self.assertTrue(payload.create_study_obj_list())
        dupe_study = {
            "requestEntries": [
                {
                    "id": "abc123",
                    "filePath": "file/path.tsv",
                    "md5": "b1d7e0a58d36502d59d036a17336ddf5",
                    "assembly": "GRCh38",
                },
                {
                    "id": "abc123",
                    "filePath": "file/path.tsv",
                    "md5": "b1d7e0a58d36502d59d036a17336ddf5",
                    "assembly": "GRCh38",
                },
            ]
        }
        payload = pl.Payload(payload=dupe_study)
        payload.create_study_obj_list()
        self.assertFalse(payload.check_study_ids_valid())

    def test_get_data_for_callback_id(self):
        payload = pl.Payload(payload=VALID_POST)
        payload.payload_to_db()
        cid = payload.callback_id
        payload_new = pl.Payload(callback_id=cid)
        for study in payload_new.study_obj_list:
            self.assertEqual(study.callback_id, cid)

    def test_get_payload__status(self):
        payload = pl.Payload(payload=VALID_POST)
        payload.payload_to_db()
        payload.get_data_for_callback_id()
        for study in payload.study_obj_list:
            study.set_retrieved_status(None)
            study.store_retrieved_status()
            study.set_data_valid_status(None)
            study.store_data_valid_status()
        status = payload.get_payload_status()
        self.assertEqual(status, "PROCESSING")
        for study in payload.study_obj_list:
            study.set_retrieved_status(0)
            study.store_retrieved_status()
            study.set_data_valid_status(0)
            study.store_data_valid_status()
        status = payload.get_payload_status()
        self.assertEqual(status, "INVALID")
        for study in payload.study_obj_list:
            study.set_retrieved_status(1)
            study.store_retrieved_status()
            study.set_data_valid_status(1)
            study.store_data_valid_status()
        status = payload.get_payload_status()
        self.assertEqual(status, "VALID")
