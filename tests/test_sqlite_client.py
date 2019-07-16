import os
import unittest
import config
from resources.sqlite_client import sqlClient
from tests.test_constants import *


class TestDB(unittest.TestCase):
    def setUp(self):
        self.testDB = "./tests/study_meta.db"
        sq = sqlClient(self.testDB)
        sq.create_conn()
        sq.cur.execute(config.DB_SCHEMA)

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
                             VALID_POST["requestEntries"][0]["pmid"],
                             VALID_POST["requestEntries"][0]["filePath"],
                             VALID_POST["requestEntries"][0]["md5"],
                             VALID_POST["requestEntries"][0]["assembly"]
                             ])
        response = sq.get_study_metadata("abc123")
        self.assertTrue(response)

    def test_cannot_insert_same_study_twice(self):
        sq = sqlClient(self.testDB)
        sq.create_conn()
        sq.insert_new_study([VALID_POST["requestEntries"][0]["id"],
                             "callback123",
                             VALID_POST["requestEntries"][0]["pmid"],
                             VALID_POST["requestEntries"][0]["filePath"],
                             VALID_POST["requestEntries"][0]["md5"],
                             VALID_POST["requestEntries"][0]["assembly"]
                             ])
        response = sq.get_study_count()
        self.assertEqual(response, 1)

    def test_can_insert_another_study(self):
        sq = sqlClient(self.testDB)
        sq.create_conn()
        sq.insert_new_study([VALID_POST["requestEntries"][0]["id"],
                             "callback123",
                             VALID_POST["requestEntries"][0]["pmid"],
                             VALID_POST["requestEntries"][0]["filePath"],
                             VALID_POST["requestEntries"][0]["md5"],
                             VALID_POST["requestEntries"][0]["assembly"]
                             ])
        sq.insert_new_study([VALID_POST["requestEntries"][1]["id"],
                             "callback234",
                             VALID_POST["requestEntries"][1]["pmid"],
                             VALID_POST["requestEntries"][1]["filePath"],
                             VALID_POST["requestEntries"][1]["md5"],
                             VALID_POST["requestEntries"][1]["assembly"]
                             ])
        response = sq.get_study_count()
        self.assertEqual(response, 2)

    def test_select_from_callback_id(self):
        sq = sqlClient(self.testDB)
        sq.create_conn()
        sq.insert_new_study([VALID_POST["requestEntries"][0]["id"],
                             "callback123",
                             VALID_POST["requestEntries"][0]["pmid"],
                             VALID_POST["requestEntries"][0]["filePath"],
                             VALID_POST["requestEntries"][0]["md5"],
                             VALID_POST["requestEntries"][0]["assembly"]
                             ])
        response = sq.get_data_from_callback_id("callback123")
        self.assertIsNotNone(response)
        self.assertEqual(response[0][0], VALID_POST["requestEntries"][0]["id"])


if __name__ == '__main__':
    unittest.main()
