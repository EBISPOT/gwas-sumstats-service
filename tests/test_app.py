import unittest
import os
from sumstats_service.app import app
from tests.test_constants import *
from sumstats_service.resources.sqlite_client import sqlClient
import sumstats_service.resources.payload as pl
import config
import requests
import requests_mock


class BasicTestCase(unittest.TestCase):
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

    def test_index(self):
        tester = app.test_client()
        response = tester.get('/', content_type='html/json')
        study_link = response.get_json()['_links']['sumstats']['href']
        self.assertEqual(response.status_code, 200)
        self.assertRegex(study_link, "http://.*sum-stats")
 
    @requests_mock.Mocker()
    def test_post_new_study(self, m):
        m.register_uri('GET', self.valid_url, content=self.valid_content)
        tester = app.test_client(self)
        response = tester.post('/sum-stats',
                               json=VALID_POST)
        self.assertEqual(response.status_code, 201)
        self.assertIn('callbackID', response.get_json())
        callback_id = response.get_json()["callbackID"]
        self.assertTrue(os.path.exists(os.path.join(config.STORAGE_PATH, callback_id)))

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
        response = tester.post('/sum-stats',
                               json=invalid_post)
        self.assertEqual(response.status_code, 400)

    @requests_mock.Mocker()
    def test_get_200_based_on_good_callback_id(self, m):
        m.register_uri('GET', self.valid_url, content=self.valid_content)
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

    @requests_mock.Mocker()
    def test_get_response_on_good_callback_id(self, m):
        m.register_uri('GET', self.valid_url, content=self.valid_content)
        tester = app.test_client(self)
        response = tester.post('/sum-stats',
                               json=VALID_POST)
        callback_id = response.get_json()["callbackID"]
        response = tester.get('/sum-stats/{}'.format(callback_id))
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["callbackID"], callback_id)
        self.assertTrue(body["completed"])
        self.assertEqual(len(body["statusList"]), 2)
        study1 = VALID_POST["requestEntries"][0]["id"]
        self.assertEqual(body["statusList"][0]["id"], study1)
        self.assertEqual(body["statusList"][0]["status"], "VALID")
        payload = pl.Payload(callback_id = callback_id)
       
    @requests_mock.Mocker()
    def test_error_when_good_file(self, m):
        m.register_uri('GET', self.valid_url, content=self.valid_content)
        tester = app.test_client(self)
        response = tester.post('/sum-stats',
                               json=VALID_POST)
        callback_id = response.get_json()["callbackID"]
        response = tester.get('/sum-stats/{}'.format(callback_id))
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["statusList"][0]["error"], None)

    @requests_mock.Mocker()
    def test_error_when_good_url_bad_md5(self, m):
        m.register_uri('GET', self.valid_url, content=self.valid_content)
        good_url_bad_md5 = {
                            "requestEntries": [
                                {
                                 "id": "abc123",
                                 "filePath": "https://valid_file.tsv",
                                 "md5":"a1195761f082f8cbc2f5a560743077ccBAD",
                                 "assembly":"38"
                                }
                              ]
                             }
        tester = app.test_client(self)
        response = tester.post('/sum-stats',
                               json=good_url_bad_md5)
        callback_id = response.get_json()["callbackID"]
        response = tester.get('/sum-stats/{}'.format(callback_id))
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["statusList"][0]["error"], "md5sum did not match the one provided")

    @requests_mock.Mocker()
    def test_error_when_bad_URL(self, m):
        bad_url1 = "NOTURLhttps://valid_file.tsv"
        bad_url2 = "https://valid_file.NONEXIST.tsv"
        m.register_uri('GET', self.valid_url, content=self.valid_content)
        m.register_uri('GET', bad_url1, exc=requests.exceptions.RequestException)
        m.register_uri('GET', bad_url2, status_code=404)
        bad_url_request = {
                    "requestEntries": [
                        {
                         "id": "abc123",
                         "filePath": bad_url1,
                         "md5":"a1195761f082f8cbc2f5a560743077cc",
                         "assembly":"38"
                        },
                        {
                         "id": "abc234",
                         "filePath": bad_url2,
                         "md5":"a1195761f082f8cbc2f5a560743077cc",
                         "assembly":"38"
                         }

                      ]
                     }

        tester = app.test_client(self)
        response = tester.post('/sum-stats',
                               json=bad_url_request)
        callback_id = response.get_json()["callbackID"]
        response = tester.get('/sum-stats/{}'.format(callback_id))
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["statusList"][0]["error"], "URL not found")
        self.assertEqual(body["statusList"][1]["error"], "URL not found")

    @requests_mock.Mocker()
    def test_validation_response_when_two_good(self, m):
        m.register_uri('GET', self.valid_url, content=self.valid_content)
        tester = app.test_client(self)
        response = tester.post('/sum-stats',
                               json=VALID_POST)
        callback_id = response.get_json()["callbackID"]
        response = tester.get('/sum-stats/{}'.format(callback_id))
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["statusList"][0]["error"], None)
        self.assertTrue(body["completed"])
        self.assertEqual(body["statusList"][0]["status"], "VALID")
        self.assertEqual(body["statusList"][1]["status"], "VALID")


if __name__ == '__main__':
    unittest.main()
