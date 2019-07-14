import os
import unittest
import config
from resources.sqlite_client import sqlClient
from tests.test_constants import *


class TestDB(unittest.TestCase):
    def setUp(self):
        self.testDB = "./tests/study_meta.db"
        sc = sqlClient(self.testDB)
        sc.create_conn()
        sc.cur.execute(config.DB_SCHEMA)

    def tearDown(self):
        os.remove(self.testDB)

    def test_database_exists(self):
        tester = os.path.exists(self.testDB)
        self.assertTrue(tester)

    def test_insert_new_study(self):
        sc = sqlClient(self.testDB)
        sc.create_conn()
        sc.insert_new_study([VALID_SET["study_id"][0],
                             VALID_SET["callback_id"][0],
                             VALID_SET["pmid"][0],
                             VALID_SET["file_path"][0],
                             VALID_SET["md5"][0],
                             VALID_SET["assembly"][0]
                             ])
        response = sc.get_study_metadata("abc123")
        self.assertTrue(response)

    def test_cannot_insert_same_study_twice(self):
        sc = sqlClient(self.testDB)
        sc.create_conn()
        sc.insert_new_study([VALID_SET["study_id"][0],
                             VALID_SET["callback_id"][0],
                             VALID_SET["pmid"][0],
                             VALID_SET["file_path"][0],
                             VALID_SET["md5"][0],
                             VALID_SET["assembly"][0]
                             ])
        response = sc.get_study_count()
        self.assertEqual(response, 1)

    def test_can_insert_another_study(self):
        sc = sqlClient(self.testDB)
        sc.create_conn()
        sc.insert_new_study([VALID_SET["study_id"][0],
                             VALID_SET["callback_id"][0],
                             VALID_SET["pmid"][0],
                             VALID_SET["file_path"][0],
                             VALID_SET["md5"][0],
                             VALID_SET["assembly"][0]
                             ])
        sc.insert_new_study(["zyx321",
                             VALID_SET["callback_id"][0],
                             VALID_SET["pmid"][0],
                             VALID_SET["file_path"][0],
                             VALID_SET["md5"][0],
                             VALID_SET["assembly"][0]
                             ])
        response = sc.get_study_count()
        self.assertEqual(response, 2)




if __name__ == '__main__':
    unittest.main()
