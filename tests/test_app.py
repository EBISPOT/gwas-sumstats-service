import os

from pymongo import MongoClient

from sumstats_service import config
from sumstats_service.app import app, celery


class TestAPP:
    def setup_method(self, method):
        self.test_storepath = "./tests/data"
        config.STORAGE_PATH = self.test_storepath
        celery.conf["CELERY_ALWAYS_EAGER"] = True
        self.valid_url = "file://{}".format(
            os.path.abspath("./tests/test_sumstats_file.tsv")
        )

    def teardown_method(self, method):
        mongo_uri = os.getenv("MONGO_URI", config.MONGO_URI)
        mongo_user = os.getenv("MONGO_USER", None)
        mongo_password = os.getenv("MONGO_PASSWORD", None)
        mongo_db = os.getenv("MONGO_DB", config.MONGO_DB)

        client = MongoClient(mongo_uri, username=mongo_user, password=mongo_password)
        client.drop_database(mongo_db)

    def test_index(self):
        tester = app.test_client(self)
        response = tester.get("/", content_type="html/json")
        assert response.status_code == 200

    def test_post_new_study_no_json(self):
        tester = app.test_client(self)
        response = tester.post("/v1/sum-stats", json=None)
        assert response.status_code == 400
        assert "callbackID" not in response.get_json()

    def test_post_new_study_missing_data(self):
        tester = app.test_client(self)
        response = tester.post("/v1/sum-stats", json="{}")
        assert response.status_code == 201
        callback_id = response.get_json()["callbackID"]
        response = tester.get("/v1/sum-stats/{}".format(callback_id))
        assert response.status_code == 200
        assert (
            "Missing 'requestEntries' in json" in response.get_json()["metadataErrors"]
        )

    def test_post_new_study_missing_mandatory_fields(self):
        tester = app.test_client(self)
        invalid_post = {
            "requestEntries": [
                {
                    "id": "xyz321",
                    "NOT_filePath": "file/path.tsv",
                    "md5": "b1d7e0a58d36502d59d036a17336ddf5",
                    "assembly": "GRCh38",
                },
            ]
        }
        response = tester.post("/v1/sum-stats", json=invalid_post)
        assert response.status_code == 201
        callback_id = response.get_json()["callbackID"]
        response = tester.get("/v1/sum-stats/{}".format(callback_id))
        assert response.status_code == 200

    def test_post_new_study_bad_id(self):
        tester = app.test_client(self)
        invalid_post = {
            "requestEntries": [
                {
                    "id": "xyz321 asd",
                    "filePath": self.valid_url,
                    "md5": "b1d7e0a58d36502d59d036a17336ddf5",
                    "assembly": "GRCh38",
                },
            ]
        }

        response = tester.post("/v1/sum-stats", json=invalid_post)
        assert response.status_code == 201
        callback_id = response.get_json()["callbackID"]
        response = tester.get("/v1/sum-stats/{}".format(callback_id))
        assert response.status_code == 200
        assert "is invalid" in response.get_json()["metadataErrors"][0]

    def test_post_duplicate_study_id_in_one_payload(self):
        tester = app.test_client(self)
        invalid_post = {
            "requestEntries": [
                {
                    "id": "abc123",
                    "filePath": self.valid_url,
                    "md5": "b1d7e0a58d36502d59d036a17336ddf5",
                    "assembly": "GRCh38",
                },
                {
                    "id": "abc123",
                    "filePath": self.valid_url,
                    "md5": "b1d7e0a58d36502d59d036a17336ddf5",
                    "assembly": "GRCh38",
                },
            ]
        }
        response = tester.post("/v1/sum-stats", json=invalid_post)
        assert response.status_code == 201
        callback_id = response.get_json()["callbackID"]
        response = tester.get("/v1/sum-stats/{}".format(callback_id))
        assert response.status_code == 200
        assert "duplicated" in response.get_json()["metadataErrors"][0]

    def test_bad_callback_id(self):
        tester = app.test_client(self)
        callback_id = "NOTINDB"
        response = tester.get("/v1/sum-stats/{}".format(callback_id))
        assert response.status_code == 404


if __name__ == "__main__":
    unittest.main()  # noqa
