import unittest
import os
import config
from sumstats_service.resources.sqlite_client import sqlClient
import sumstats_service.resources.study_service as st


class TestStudyService(unittest.TestCase):
    def setUp(self):
        self.testDB = "./tests/study_meta.db"
        config.DB_PATH = self.testDB
        sq = sqlClient(self.testDB)
        sq.create_conn()
        sq.cur.execute(config.DB_SCHEMA)

    def tearDown(self):
        os.remove(self.testDB)

    def test_valid_study_id(self):
        study_id = "123abc123"
        pmid = "12324567"
        file_path = "file/path.tsv"
        md5 = "b1d7e0a58d36502d59d036a17336ddf5"
        assembly = "38"
        study = st.Study(study_id=study_id, pmid=pmid, file_path=file_path, md5=md5, assembly=assembly)
        self.assertTrue(study.valid_study_id())
        # invalid study id
        study_id = "asd1232 asd"
        study = st.Study(study_id=study_id, pmid=pmid, file_path=file_path, md5=md5, assembly=assembly)
        self.assertFalse(study.valid_study_id())

    def test_create_entry_for_study(self):
        study_id = "123abc123"
        pmid = "12324567"
        callback_id = "abc123xyz"
        file_path = "file/path.tsv"
        md5 = "b1d7e0a58d36502d59d036a17336ddf5"
        assembly = "38"
        study = st.Study(study_id=study_id, pmid=pmid, file_path=file_path, md5=md5, assembly=assembly, callback_id=callback_id)
        study.create_entry_for_study()
        check = study.get_study_from_db()
        self.assertIsNotNone(check)
        self.assertEqual(check[0], study_id)

    def test_update_retrieved_status(self):
        study_id = "123abc123"
        pmid = "12324567"
        callback_id = "abc123xyz"
        file_path = "file/path.tsv"
        md5 = "b1d7e0a58d36502d59d036a17336ddf5"
        assembly = "38"
        study = st.Study(study_id=study_id, pmid=pmid, file_path=file_path, md5=md5, assembly=assembly, callback_id=callback_id)
        study.create_entry_for_study()
        check = study.get_study_from_db()
        self.assertIsNone(check[6])
        study.update_retrieved_status(1)
        check = study.get_study_from_db()
        self.assertEqual(check[6], 1)

    def test_update_data_valid_status(self):
        study_id = "123abc123"
        pmid = "12324567"
        callback_id = "abc123xyz"
        file_path = "file/path.tsv"
        md5 = "b1d7e0a58d36502d59d036a17336ddf5"
        assembly = "38"
        study = st.Study(study_id=study_id, pmid=pmid, file_path=file_path, md5=md5, assembly=assembly, callback_id=callback_id)
        study.create_entry_for_study()
        check = study.get_study_from_db()
        self.assertIsNone(check[7])
        study.update_data_valid_status(1)
        check = study.get_study_from_db()
        self.assertEqual(check[7], 1)

    def test_get_statuses(self):
        study_id = "123abc123"
        pmid = "12324567"
        callback_id = "abc123xyz"
        file_path = "file/path.tsv"
        md5 = "b1d7e0a58d36502d59d036a17336ddf5"
        assembly = "38"
        study = st.Study(study_id=study_id, pmid=pmid, file_path=file_path, md5=md5, assembly=assembly, callback_id=callback_id)
        study.create_entry_for_study()
        study.get_study_from_db()
        self.assertEqual(study.get_status(), 'VALIDATING')
        study.update_retrieved_status(0)
        study.get_study_from_db()
        self.assertEqual(study.get_status(), 'INVALID')
        study.update_retrieved_status(1)
        study.get_study_from_db()
        self.assertEqual(study.get_status(), 'VALIDATING')
        study.update_data_valid_status(0)
        study.get_study_from_db()
        self.assertEqual(study.get_status(), 'INVALID')
        study.update_data_valid_status(1)
        study.get_study_from_db()
        self.assertEqual(study.get_status(), 'VALID')


if __name__ == '__main__':
    unittest.main()
