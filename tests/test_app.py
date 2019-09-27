import pytest
import os
import shutil
import json
from sumstats_service.app import app
import sumstats_service.resources.api_endpoints as ep
import sumstats_service.resources.api_utils as au
from tests.test_constants import *
from sumstats_service.resources.sqlite_client import sqlClient
import sumstats_service.resources.payload as pl
import config


class TestAPP:
    def setup_method(self, method):
        self.testDB = "./tests/study_meta.db"
        self.test_storepath = "./tests/data"
        config.STORAGE_PATH = self.test_storepath
        config.DB_PATH = self.testDB
        sq = sqlClient(self.testDB)
        sq.create_conn()
        sq.cur.executescript(config.DB_SCHEMA)
        self.valid_url = "file://{}".format(os.path.abspath("./tests/test_sumstats_file.tsv"))
            
    def teardown_method(self, method):
        os.remove(self.testDB)

    def test_index(self):
        tester = app.test_client(self)
        response = tester.get('/', content_type='html/json')
        study_link = response.get_json()['_links']['sumstats']['href']
        assert response.status_code == 200

    def test_get_200_based_on_good_callback_id(self, celery_session_worker):
        valid_json = {
               "requestEntries": [
                   {
                    "id": "abc123",
                    "filePath": self.valid_url,
                    "md5":"a1195761f082f8cbc2f5a560743077cc",
                    "assembly":"38"
                   },
                   {
                    "id": "xyz321",
                    "filePath": self.valid_url,
                    "md5":"a1195761f082f8cbc2f5a560743077cc",
                    "assembly":"38"
                   },
                 ]
               } 
        tester = app.test_client(self)
        response = tester.post('/v1/sum-stats', json=valid_json)
        assert response.status_code == 201
        callback_id = response.get_json()["callbackID"]
        response = tester.get('/v1/sum-stats/{}'.format(callback_id))
        assert response.status_code == 200

    def test_post_new_study_no_json(self):
        tester = app.test_client(self)
        response = tester.post('/v1/sum-stats',
                               json=None)
        assert response.status_code == 400
        assert 'callbackID' not in response.get_json()

    def test_post_new_study_missing_data(self):
        tester = app.test_client(self)
        response = tester.post('/v1/sum-stats',
                               json='{}')
        assert response.status_code == 400
        assert "Missing 'requestEntries' in json" in response.get_json()['message']

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
        response = tester.post('/v1/sum-stats',
                               json=invalid_post)
        assert response.status_code == 400
        assert "Missing field" in response.get_json()['message']

    def test_post_new_study_bad_id(self):
        tester = app.test_client(self)
        invalid_post = {
                        "requestEntries": [
                          {
                            "id": "xyz321 asd",
                            "filePath": self.valid_url,
                            "md5":"b1d7e0a58d36502d59d036a17336ddf5",
                            "assembly":"38"
                           },
                         ]
                       }

        response = tester.post('/v1/sum-stats',
                               json=invalid_post)
        assert response.status_code == 400
        assert "is invalid" in response.get_json()['message']

    def test_post_duplicate_study_id_in_one_payload(self):
        tester = app.test_client(self)
        invalid_post = {
                        "requestEntries": [
                            {
                             "id": "abc123",
                             "filePath": self.valid_url,
                             "md5":"b1d7e0a58d36502d59d036a17336ddf5",
                             "assembly":"38"
                            },
                            {
                             "id": "abc123",
                             "filePath": self.valid_url,
                             "md5":"b1d7e0a58d36502d59d036a17336ddf5",
                             "assembly":"38"
                            },
                          ]
                        }
        response = tester.post('/v1/sum-stats',
                               json=invalid_post)
        assert response.status_code == 400

    def test_bad_callback_id(self):
        tester = app.test_client(self)
        callback_id = 'NOTINDB'
        response = tester.get('/v1/sum-stats/{}'.format(callback_id))
        assert response.status_code == 404

    def test_delete_payload(self):
        valid_json = {
               "requestEntries": [
                   {
                    "id": "abc123",
                    "filePath": self.valid_url,
                    "md5":"a1195761f082f8cbc2f5a560743077cc",
                    "assembly":"38"
                   },
                   {
                    "id": "xyz321",
                    "filePath": self.valid_url,
                    "md5":"a1195761f082f8cbc2f5a560743077cc",
                    "assembly":"38"
                   },
                 ]
               } 
        tester = app.test_client(self)
        response = tester.post('/v1/sum-stats', json=valid_json)
        assert response.status_code == 201
        callback_id = response.get_json()["callbackID"]
        response = tester.get('/v1/sum-stats/{}'.format(callback_id))
        assert response.status_code == 200
        response = tester.delete('/v1/sum-stats/{}'.format(callback_id))
        assert response.status_code == 200
        response = tester.get('/v1/sum-stats/{}'.format(callback_id))
        assert response.status_code == 404
        response = tester.delete('/v1/sum-stats/{}'.format(callback_id))
        assert response.status_code == 404


    def test_get_200_with_readme(self, celery_session_worker):
        valid_json = {
               "requestEntries": [
                   {
                    "id": "abc123",
                    "filePath": self.valid_url,
                    "readme": TEST_README,
                    "md5":"a1195761f082f8cbc2f5a560743077cc",
                    "assembly":"38"
                   },
                   {
                    "id": "xyz321",
                    "filePath": self.valid_url,
                    "md5":"a1195761f082f8cbc2f5a560743077cc",
                    "assembly":"38"
                   },
                 ]
               } 
        tester = app.test_client(self)
        response = tester.post('/v1/sum-stats', json=valid_json)
        assert response.status_code == 201
        callback_id = response.get_json()["callbackID"]
        response = tester.get('/v1/sum-stats/{}'.format(callback_id))
        assert response.status_code == 200



if __name__ == '__main__':
    unittest.main()
