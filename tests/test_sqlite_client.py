import os
import unittest
import config
from sumstats_service.resources.sqlite_client import sqlClient
from tests.test_constants import *


class TestDB(unittest.TestCase):
    def setUp(self):
        self.testDB = "./tests/study_meta.db"
        self.test_storepath = "./tests/data"
        config.STORAGE_PATH = self.test_storepath
        config.BROKER_PORT = 5682
        config.BROKER_HOST = "localhost"
        sq = sqlClient(self.testDB)
        sq.create_conn()
        sq.cur.executescript(config.DB_SCHEMA)

    def tearDown(self):
        os.remove(self.testDB)

    def test_database_exists(self):
        tester = os.path.exists(self.testDB)
        self.assertTrue(tester)

    def test_insert_new_study(self):
        sq = sqlClient(self.testDB)
        sq.create_conn()
        sq.insert_new_study([VALID_POST["requestEntries"][0]["id"],
                             "callback123",
                             VALID_POST["requestEntries"][0]["filePath"],
                             VALID_POST["requestEntries"][0]["md5"],
                             VALID_POST["requestEntries"][0]["assembly"],
                             VALID_POST["requestEntries"][0]["readme"],
                             VALID_POST["requestEntries"][0]["entryUUID"]
                             ])
        response = sq.get_study_metadata("abc123")
        self.assertTrue(response)

    def test_cannot_insert_same_study_twice(self):
        sq = sqlClient(self.testDB)
        sq.create_conn()
        sq.insert_new_study([VALID_POST["requestEntries"][0]["id"],
                             "callback123",
                             VALID_POST["requestEntries"][0]["filePath"],
                             VALID_POST["requestEntries"][0]["md5"],
                             VALID_POST["requestEntries"][0]["assembly"],
                             VALID_POST["requestEntries"][0]["readme"],
                             VALID_POST["requestEntries"][0]["entryUUID"]
                             ])
        response = sq.get_study_count()
        self.assertEqual(response, 1)

    def test_can_insert_another_study(self):
        sq = sqlClient(self.testDB)
        sq.create_conn()
        sq.insert_new_study([VALID_POST["requestEntries"][0]["id"],
                             "callback123",
                             VALID_POST["requestEntries"][0]["filePath"],
                             VALID_POST["requestEntries"][0]["md5"],
                             VALID_POST["requestEntries"][0]["assembly"],
                             VALID_POST["requestEntries"][0]["readme"],
                             VALID_POST["requestEntries"][0]["entryUUID"]
                             ])
        sq.insert_new_study([VALID_POST["requestEntries"][1]["id"],
                             "callback234",
                             VALID_POST["requestEntries"][1]["filePath"],
                             VALID_POST["requestEntries"][1]["md5"],
                             VALID_POST["requestEntries"][1]["assembly"],
                             None,
                             None
                             ])
        response = sq.get_study_count()
        self.assertEqual(response, 2)

    def test_select_from_callback_id(self):
        sq = sqlClient(self.testDB)
        sq.create_conn()
        sq.insert_new_study([VALID_POST["requestEntries"][0]["id"],
                             "callback123",
                             VALID_POST["requestEntries"][0]["filePath"],
                             VALID_POST["requestEntries"][0]["md5"],
                             VALID_POST["requestEntries"][0]["assembly"],
                             VALID_POST["requestEntries"][0]["readme"],
                             VALID_POST["requestEntries"][0]["entryUUID"]
                             ])
        sq.insert_new_study([VALID_POST["requestEntries"][1]["id"],
                             "callback123",
                             VALID_POST["requestEntries"][0]["filePath"],
                             VALID_POST["requestEntries"][0]["md5"],
                             VALID_POST["requestEntries"][0]["assembly"],
                             VALID_POST["requestEntries"][0]["readme"],
                             VALID_POST["requestEntries"][0]["entryUUID"]
                             ])
        response = sq.get_data_from_callback_id("callback123")
        self.assertIsNotNone(response)
        self.assertEqual(len(response),2)
        self.assertEqual(response[0][0], VALID_POST["requestEntries"][0]["id"])
        self.assertEqual(response[1][0], VALID_POST["requestEntries"][1]["id"])

    def test_update_retrieved_status(self):
        sq = sqlClient(self.testDB)
        sq.create_conn()
        sq.insert_new_study([VALID_POST["requestEntries"][0]["id"],
                             "callback123",
                             VALID_POST["requestEntries"][0]["filePath"],
                             VALID_POST["requestEntries"][0]["md5"],
                             VALID_POST["requestEntries"][0]["assembly"],
                             VALID_POST["requestEntries"][0]["readme"],
                             VALID_POST["requestEntries"][0]["entryUUID"]
                             ])
        sq.update_retrieved_status(VALID_POST["requestEntries"][0]["id"], 1)
        response = sq.get_study_metadata(VALID_POST["requestEntries"][0]["id"])
        self.assertEqual(response[5], 1)
        sq.update_retrieved_status(VALID_POST["requestEntries"][0]["id"], 0)
        response = sq.get_study_metadata(VALID_POST["requestEntries"][0]["id"])
        self.assertEqual(response[5], 0)

    def test_update_data_valid_status(self):
        sq = sqlClient(self.testDB)
        sq.create_conn()
        sq.insert_new_study([VALID_POST["requestEntries"][0]["id"],
                             "callback123",
                             VALID_POST["requestEntries"][0]["filePath"],
                             VALID_POST["requestEntries"][0]["md5"],
                             VALID_POST["requestEntries"][0]["assembly"],
                             VALID_POST["requestEntries"][0]["readme"],
                             VALID_POST["requestEntries"][0]["entryUUID"]
                             ])
        sq.update_data_valid_status(VALID_POST["requestEntries"][0]["id"], 1)
        response = sq.get_study_metadata(VALID_POST["requestEntries"][0]["id"])
        self.assertEqual(response[6], 1)
        sq.update_data_valid_status(VALID_POST["requestEntries"][0]["id"], 0)
        response = sq.get_study_metadata(VALID_POST["requestEntries"][0]["id"])
        self.assertEqual(response[6], 0)

    def test_update_error_code(self):
        sq = sqlClient(self.testDB)
        sq.create_conn()
        sq.insert_new_study([VALID_POST["requestEntries"][0]["id"],
                             "callback123",
                             VALID_POST["requestEntries"][0]["filePath"],
                             VALID_POST["requestEntries"][0]["md5"],
                             VALID_POST["requestEntries"][0]["assembly"],
                             VALID_POST["requestEntries"][0]["readme"],
                             VALID_POST["requestEntries"][0]["entryUUID"]
                             ])
        sq.update_error_code(VALID_POST["requestEntries"][0]["id"], 1)
        response = sq.get_study_metadata(VALID_POST["requestEntries"][0]["id"])
        self.assertEqual(response[7], 1)
        sq.update_error_code(VALID_POST["requestEntries"][0]["id"], None)
        response = sq.get_study_metadata(VALID_POST["requestEntries"][0]["id"])
        self.assertEqual(response[7], None)

    def test_error_message_retrieval(self):
        sq = sqlClient(self.testDB)
        sq.create_conn()
        response = sq.get_error_message_from_code(1)
        self.assertEqual(response, "The summary statistics file cannot be found")
        response = sq.get_error_message_from_code(0)
        self.assertIsNone(response)


if __name__ == '__main__':
    unittest.main()
