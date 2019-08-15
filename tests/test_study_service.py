import unittest
import os
import config
from sumstats_service.resources.sqlite_client import sqlClient
import sumstats_service.resources.study_service as st


class TestStudyService(unittest.TestCase):
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

    def test_valid_study_id(self):
        study_id = "123abc123"
        file_path = "file/path.tsv"
        md5 = "b1d7e0a58d36502d59d036a17336ddf5"
        assembly = "38"
        study = st.Study(study_id=study_id, file_path=file_path, md5=md5, assembly=assembly)
        self.assertTrue(study.valid_study_id())
        # invalid study id
        study_id = "asd1232 asd"
        study = st.Study(study_id=study_id, file_path=file_path, md5=md5, assembly=assembly)
        self.assertFalse(study.valid_study_id())

    def test_create_entry_for_study(self):
        study_id = "123abc123"
        callback_id = "abc123xyz"
        file_path = "file/path.tsv"
        md5 = "b1d7e0a58d36502d59d036a17336ddf5"
        assembly = "38"
        study = st.Study(study_id=study_id, file_path=file_path, md5=md5, assembly=assembly, callback_id=callback_id)
        study.create_entry_for_study()
        check = study.get_study_from_db()
        self.assertIsNotNone(check)
        self.assertEqual(check[0], study_id)

    def test_update_retrieved_status(self):
        study_id = "123abc123"
        callback_id = "abc123xyz"
        file_path = "file/path.tsv"
        md5 = "b1d7e0a58d36502d59d036a17336ddf5"
        assembly = "38"
        study = st.Study(study_id=study_id, file_path=file_path, md5=md5, assembly=assembly, callback_id=callback_id)
        study.create_entry_for_study()
        check = study.get_study_from_db()
        self.assertIsNone(check[5])
        study.set_retrieved_status(1)
        study.store_retrieved_status()
        check = study.get_study_from_db()
        self.assertEqual(check[5], 1)

    def test_update_data_valid_status(self):
        study_id = "123abc123"
        callback_id = "abc123xyz"
        file_path = "file/path.tsv"
        md5 = "b1d7e0a58d36502d59d036a17336ddf5"
        assembly = "38"
        study = st.Study(study_id=study_id, file_path=file_path, md5=md5, assembly=assembly, callback_id=callback_id)
        study.create_entry_for_study()
        check = study.get_study_from_db()
        self.assertIsNone(check[6])
        study.set_data_valid_status(1)
        study.store_data_valid_status()
        check = study.get_study_from_db()
        self.assertEqual(check[6], 1)

    def test_get_statuses(self):
        study_id = "123abc123"
        callback_id = "abc123xyz"
        file_path = "file/path.tsv"
        md5 = "b1d7e0a58d36502d59d036a17336ddf5"
        assembly = "38"
        study = st.Study(study_id=study_id, file_path=file_path, md5=md5, assembly=assembly, callback_id=callback_id)
        study.create_entry_for_study()
        study.get_study_from_db()
        self.assertEqual(study.get_status(), 'RETRIEVING')
        study.set_retrieved_status(0)
        study.store_retrieved_status()
        study.get_study_from_db()
        self.assertEqual(study.get_status(), 'INVALID')
        study.set_retrieved_status(1)
        study.store_retrieved_status()
        study.get_study_from_db()
        self.assertEqual(study.get_status(), 'VALIDATING')
        study.set_data_valid_status(0)
        study.store_data_valid_status()
        study.get_study_from_db()
        self.assertEqual(study.get_status(), 'INVALID')
        study.set_data_valid_status(1)
        study.store_data_valid_status()
        study.get_study_from_db()
        self.assertEqual(study.get_status(), 'VALID')

    def test_update_error(self):
        study_id = "123abc123"
        callback_id = "abc123xyz"
        file_path = "file/path.tsv"
        md5 = "b1d7e0a58d36502d59d036a17336ddf5"
        assembly = "38"
        study = st.Study(study_id=study_id, file_path=file_path, md5=md5, assembly=assembly, callback_id=callback_id)
        study.create_entry_for_study()
        study.get_study_from_db()
        self.assertIsNone(study.error_code)
        self.assertIsNone(study.error_text)
        study.set_error_code(1)
        study.store_error_code()
        study.get_study_from_db()
        self.assertEqual(study.error_code, 1)
        self.assertEqual(study.error_text, "URL not found")
        study.set_error_code(None)
        study.store_error_code()
        study.get_study_from_db()
        self.assertEqual(study.error_code, None)
        self.assertEqual(study.error_text, None)


if __name__ == '__main__':
    unittest.main()
