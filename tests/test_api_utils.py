import unittest
import os
import config
from tests.test_constants import *
import resources.api_utils as au
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
        self.assertIsNotNone(au.generate_callback_id())

    def test_parse_new_study_json(self):
        data = {
                 "id": "xyz321",
                 "pmid": "1233454",
                 "filePath": "file/path.tsv",
                 "md5":"b1d7e0a58d36502d59d036a17336ddf5",
                 "assembly":"38"
                }
        result = au.parse_new_study_json(data)
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
        self.assertRaises(BadUserRequest, au.parse_new_study_json, data_missing_field)

    def test_check_basic_content_present(self):
        data = {'requestEntries': [{}]}
        self.assertTrue(au.check_basic_content_present(data))
        missing_data = {'requestEntries': []}
        self.assertRaises(BadUserRequest, au.check_basic_content_present, missing_data)
        missing_all = {}
        self.assertRaises(BadUserRequest, au.check_basic_content_present, missing_all)

    def test_check_study_ids_ok(self):
        self.assertTrue(au.check_study_ids_ok(VALID_POST))
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
        self.assertRaises(BadUserRequest, au.check_study_ids_ok, dupe_study)
        







if __name__ == '__main__':
    unittest.main()
