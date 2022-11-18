import unittest
import os
from sumstats_service import config
from sumstats_service.resources.sqlite_client import sqlClient
import sumstats_service.resources.study_service as st
from pymongo import MongoClient


class TestStudyService(unittest.TestCase):
    def setUp(self):
        self.testDB = "./tests/study_meta.db"
        self.test_storepath = "./tests/data"
        config.STORAGE_PATH = self.test_storepath
        config.DB_PATH = self.testDB
        config.BROKER_PORT = 5682
        config.BROKER_HOST = "localhost"
        sq = sqlClient(self.testDB)
        sq.create_conn()
        sq.cur.executescript(config.DB_SCHEMA)
        
        self.study_id = "123abc123"
        self.callback_id = "abc123xyz"
        self.file_path = "path.tsv"
        self.entryUUID = "ABC1234"
        self.md5 = "b1d7e0a58d36502d59d036a17336ddf5"
        self.assembly = "GRCh38"


    def tearDown(self):
        os.remove(self.testDB)
        client = MongoClient(config.MONGO_URI)
        client.drop_database(config.MONGO_DB)


    def test_valid_study_id(self):
        study = st.Study(study_id=self.study_id, file_path=self.file_path, md5=self.md5, assembly=self.assembly)
        self.assertTrue(study.valid_study_id())
        # invalid study id
        study_id = "asd1232 asd"
        study = st.Study(study_id=study_id, file_path=self.file_path, md5=self.md5, assembly=self.assembly)
        self.assertFalse(study.valid_study_id())

    def test_create_entry_for_study(self):
        study = st.Study(study_id=self.study_id, file_path=self.file_path, md5=self.md5, assembly=self.assembly)
        study.create_entry_for_study()
        check = study.get_study_from_db()
        self.assertIsNotNone(check)
        self.assertEqual(check['studyID'], self.study_id)

    def test_update_retrieved_status(self):
        study = st.Study(study_id=self.study_id, file_path=self.file_path, md5=self.md5, assembly=self.assembly)
        study.create_entry_for_study()
        check = study.get_study_from_db()
        self.assertTrue('retrieved' not in check)
        study.set_retrieved_status(1)
        study.store_retrieved_status()
        check = study.get_study_from_db()
        self.assertEqual(check['retrieved'], 1)

    def test_update_data_valid_status(self):
        study = st.Study(study_id=self.study_id, file_path=self.file_path, md5=self.md5, assembly=self.assembly)
        study.create_entry_for_study()
        check = study.get_study_from_db()
        self.assertTrue('dataValid' not in check)
        study.set_data_valid_status(1)
        study.store_data_valid_status()
        check = study.get_study_from_db()
        self.assertEqual(check['dataValid'], 1)

    def test_get_statuses(self):
        study = st.Study(study_id=self.study_id, file_path=self.file_path, md5=self.md5, assembly=self.assembly)
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
        study = st.Study(study_id=self.study_id, file_path=self.file_path, md5=self.md5, assembly=self.assembly)
        study.create_entry_for_study()
        study.get_study_from_db()
        self.assertIsNone(study.error_code)
        self.assertIsNone(study.error_text)
        study.set_error_code(1)
        study.store_error_code()
        study.get_study_from_db()
        self.assertEqual(study.error_code, 1)
        self.assertEqual(study.error_text, "The summary statistics file cannot be found")
        study.set_error_code(None)
        study.store_error_code()
        study.get_study_from_db()
        self.assertEqual(study.error_code, None)
        self.assertEqual(study.error_text, None)

    def test_valid_assembly(self):
        study = st.Study(study_id=self.study_id, file_path=self.file_path, md5=self.md5, assembly=self.assembly)
        self.assertTrue(study.valid_assembly())
        study = st.Study(study_id=self.study_id, file_path=self.file_path, md5=self.md5, assembly="FAIL")
        self.assertFalse(study.valid_assembly())

    def test_mandatory_metadata_check(self):
        study = st.Study(study_id=self.study_id, file_path=self.file_path, md5=self.md5, assembly=self.assembly)
        self.assertTrue(study.mandatory_metadata_check())
        study = st.Study(study_id=self.study_id, file_path=self.file_path, md5=self.md5, assembly="")
        self.assertFalse(study.mandatory_metadata_check())
        study = st.Study(study_id=self.study_id, file_path=None, md5=self.md5, assembly=self.assembly)
        self.assertFalse(study.mandatory_metadata_check())

    def test_validate_study_missing_metadata(self):
        study = st.Study(study_id=self.study_id, file_path=self.file_path, md5=self.md5, assembly="")
        study.validate_study()
        self.assertEqual(study.error_code, 4)

    def test_validate_study_metadata_invalid(self):
        study = st.Study(study_id=self.study_id, file_path=self.file_path, md5=self.md5, assembly="FAIL")
        study.mandatory_metadata_check()
        self.assertEqual(study.error_code, 5)

    def test_validate_study_invalid_file_path(self):
        study = st.Study(study_id=self.study_id, file_path=self.file_path, md5=self.md5, assembly=self.assembly,
                         callback_id="1234abcd", entryUUID=self.entryUUID)
        study.validate_study()
        self.assertEqual(study.error_code, 1)

    def test_validate_study_md5_invalid(self):
        valid_file = "test_sumstats_file.tsv"
        study = st.Study(study_id=self.study_id, file_path=valid_file, md5=self.md5, assembly=self.assembly,
                         callback_id="1234abcd", entryUUID=self.entryUUID)
        study.validate_study()
        self.assertEqual(study.error_code, 2)



if __name__ == '__main__':
    unittest.main()
