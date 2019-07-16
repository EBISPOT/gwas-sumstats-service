import unittest
import os
from app import app
from test_constants import *
from resources.sqlite_client import sqlClient
import config


class BasicTestCase(unittest.TestCase):
    def setUp(self):
        self.testDB = "./tests/study_meta.db"
        config.DB_PATH = self.testDB 
        sq = sqlClient(self.testDB)
        sq.create_conn()
        sq.cur.execute(config.DB_SCHEMA)

    def tearDown(self):
        os.remove(self.testDB)

    def test_index(self):
        tester = app.test_client()
        response = tester.get('/', content_type='html/json')
        study_link = response.get_json()['_links']['sumstats']['href']
        self.assertEqual(response.status_code, 200)
        self.assertRegex(study_link, "http://.*sum-stats")

    def test_post_new_study(self):
        tester = app.test_client(self)
        response = tester.post('/sum-stats', 
                               json=VALID_POST)
        self.assertEqual(response.status_code, 201)
        self.assertIn('callbackID', response.get_json())

    def test_post_new_study_no_json(self):
        tester = app.test_client(self)
        response = tester.post('/sum-stats',
                               json=None)
        self.assertEqual(response.status_code, 400)
        self.assertNotIn('callbackID', response.get_json())

    def test_post_new_study_missing_data(self):
        tester = app.test_client(self)
        response = tester.post('/sum-stats',
                               json='{}')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Missing 'requestEntries' in json", response.get_json()['message'])

    def test_post_new_study_missing_mandatory_fields(self):
        tester = app.test_client(self)
        invalid_post = { 
                        "requestEntries": [
                          {
                            "id": "xyz321",
                            "pmid": "1233454",
                            "NOT_filePath": "file/path.tsv",
                            "md5":"b1d7e0a58d36502d59d036a17336ddf5",
                            "assembly":"38"
                           },
                         ]
                       }
        response = tester.post('/sum-stats',
                               json=invalid_post)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Missing field", response.get_json()['message'])

    def test_post_new_study_bad_id(self):
        tester = app.test_client(self)
        invalid_post = { 
                        "requestEntries": [
                          {
                            "id": "xyz321 asd",
                            "pmid": "1233454",
                            "filePath": "file/path.tsv",
                            "md5":"b1d7e0a58d36502d59d036a17336ddf5",
                            "assembly":"38"
                           },
                         ]
                       }

        response = tester.post('/sum-stats',
                               json=invalid_post)
        self.assertEqual(response.status_code, 400)
        self.assertIn("is invalid", response.get_json()['message'])
 
    def test_post_duplicate_study_id_in_one_payload(self):
        tester = app.test_client(self)
        invalid_post = { 
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
        response = tester.post('/sum-stats',
                               json=invalid_post)
        self.assertEqual(response.status_code, 400)

    def test_get_200_based_on_good_callback_id(self):
        tester = app.test_client(self)
        response = tester.post('/sum-stats', 
                               json=VALID_POST)
        callback_id = response.get_json()["callbackID"]
        response = tester.get('/sum-stats/{}'.format(callback_id))
        self.assertEqual(response.status_code, 200)
        
    def test_bad_callback_id(self):
        tester = app.test_client(self)
        callback_id = 'NOTINDB'
        response = tester.get('/sum-stats/{}'.format(callback_id))
        self.assertEqual(response.status_code, 404)

        


        


if __name__ == '__main__':
    unittest.main()
