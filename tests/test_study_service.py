import os
import shutil
import unittest

from pymongo import MongoClient

import sumstats_service.resources.study_service as st
from sumstats_service import config


class TestStudyService(unittest.TestCase):
    def setUp(self):
        self.test_storepath = "./tests/data"
        config.STORAGE_PATH = self.test_storepath
        config.BROKER_PORT = 5682
        config.BROKER_HOST = "localhost"
        config.DEPO_PATH = "./tests"
        self.study_id = "123abc123"
        self.callback_id = "abc123xyz"
        self.file_path = "path.tsv"
        self.entryUUID = "ABC1234"
        self.md5 = "b1d7e0a58d36502d59d036a17336ddf5"
        self.valid_file_md5 = "9b5f307016408b70cde2c9342648aa9b"
        self.assembly = "GRCh38"
        self.valid_file = "test_sumstats_file.tsv"
        self.file_zero_p_values = "test_sumstats_file_zero_p_values.tsv"
        self.md5_file_zero_p_values = "912032fda7691a6e811f54bc66168f98"
        self.test_validate_path = os.path.join(config.VALIDATED_PATH, self.callback_id)
        os.makedirs(config.STORAGE_PATH, exist_ok=True)
        os.makedirs(self.test_validate_path, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_storepath)
        shutil.rmtree(self.test_validate_path)

        mongo_uri = os.getenv("MONGO_URI", config.MONGO_URI)
        mongo_user = os.getenv("MONGO_USER", None)
        mongo_password = os.getenv("MONGO_PASSWORD", None)
        mongo_db = os.getenv("MONGO_DB", config.MONGO_DB)

        client = MongoClient(mongo_uri, username=mongo_user, password=mongo_password)
        client.drop_database(mongo_db)

    def test_valid_study_id(self):
        study = st.Study(
            study_id=self.study_id,
            file_path=self.file_path,
            md5=self.md5,
            assembly=self.assembly,
        )
        self.assertTrue(study.valid_study_id())
        # invalid study id
        study_id = "asd1232 asd"
        study = st.Study(
            study_id=study_id,
            file_path=self.file_path,
            md5=self.md5,
            assembly=self.assembly,
        )
        self.assertFalse(study.valid_study_id())

    def test_create_entry_for_study(self):
        study = st.Study(
            study_id=self.study_id,
            file_path=self.file_path,
            md5=self.md5,
            assembly=self.assembly,
        )
        study.create_entry_for_study()
        check = study.get_study_from_db()
        self.assertIsNotNone(check)
        self.assertEqual(check["studyID"], self.study_id)

    def test_update_retrieved_status(self):
        study = st.Study(
            study_id=self.study_id,
            file_path=self.file_path,
            md5=self.md5,
            assembly=self.assembly,
        )
        study.create_entry_for_study()
        check = study.get_study_from_db()
        self.assertTrue("retrieved" not in check)
        study.set_retrieved_status(1)
        study.store_retrieved_status()
        check = study.get_study_from_db()
        self.assertEqual(check["retrieved"], 1)

    def test_update_data_valid_status(self):
        study = st.Study(
            study_id=self.study_id,
            file_path=self.file_path,
            md5=self.md5,
            assembly=self.assembly,
        )
        study.create_entry_for_study()
        check = study.get_study_from_db()
        self.assertTrue("dataValid" not in check)
        study.set_data_valid_status(1)
        study.store_data_valid_status()
        check = study.get_study_from_db()
        self.assertEqual(check["dataValid"], 1)

    def test_get_statuses(self):
        study = st.Study(
            study_id=self.study_id,
            file_path=self.file_path,
            md5=self.md5,
            assembly=self.assembly,
        )
        study.create_entry_for_study()
        study.get_study_from_db()
        self.assertEqual(study.get_status(), "RETRIEVING")
        study.set_retrieved_status(0)
        study.store_retrieved_status()
        study.get_study_from_db()
        self.assertEqual(study.get_status(), "INVALID")
        study.set_retrieved_status(1)
        study.store_retrieved_status()
        study.get_study_from_db()
        self.assertEqual(study.get_status(), "VALIDATING")
        study.set_data_valid_status(0)
        study.store_data_valid_status()
        study.get_study_from_db()
        self.assertEqual(study.get_status(), "INVALID")
        study.set_data_valid_status(1)
        study.store_data_valid_status()
        study.get_study_from_db()
        self.assertEqual(study.get_status(), "VALID")

    def test_update_error(self):
        study = st.Study(
            study_id=self.study_id,
            file_path=self.file_path,
            md5=self.md5,
            assembly=self.assembly,
        )
        study.create_entry_for_study()
        study.get_study_from_db()
        self.assertIsNone(study.error_code)
        self.assertIsNone(study.error_text)
        study.set_error_code(1)
        study.store_error_code()
        study.get_study_from_db()
        self.assertEqual(study.error_code, 1)
        self.assertEqual(
            study.error_text, "The summary statistics file cannot be found"
        )
        study.set_error_code(None)
        study.store_error_code()
        study.get_study_from_db()
        self.assertEqual(study.error_code, None)
        self.assertEqual(study.error_text, None)

    def test_valid_assembly(self):
        study = st.Study(
            study_id=self.study_id,
            file_path=self.file_path,
            md5=self.md5,
            assembly=self.assembly,
        )
        self.assertTrue(study.valid_assembly())
        study = st.Study(
            study_id=self.study_id,
            file_path=self.file_path,
            md5=self.md5,
            assembly="FAIL",
        )
        self.assertFalse(study.valid_assembly())

    def test_mandatory_metadata_check(self):
        study = st.Study(
            study_id=self.study_id,
            file_path=self.file_path,
            md5=self.md5,
            assembly=self.assembly,
        )
        self.assertTrue(study.mandatory_metadata_check())
        study = st.Study(
            study_id=self.study_id, file_path=self.file_path, md5=self.md5, assembly=""
        )
        self.assertFalse(study.mandatory_metadata_check())
        study = st.Study(
            study_id=self.study_id, file_path=None, md5=self.md5, assembly=self.assembly
        )
        self.assertFalse(study.mandatory_metadata_check())

    def test_retrieve_file(self):
        study = st.Study(
            study_id=self.study_id,
            file_path=self.valid_file,
            callback_id="1234abcd",
            entryUUID=self.entryUUID,
        )
        study.retrieve_study_file()
        self.assertEqual(study.retrieved, 1)

    def test_validate_study_missing_metadata(self):
        study = st.Study(
            study_id=self.study_id,
            file_path=self.valid_file,
            md5=self.md5,
            assembly="",
            callback_id="1234abcd",
            entryUUID=self.entryUUID,
        )
        study.retrieve_study_file()
        study.validate_study()
        self.assertEqual(study.error_code, 4)

    def test_validate_study_metadata_invalid(self):
        study = st.Study(
            study_id=self.study_id,
            file_path=self.file_path,
            md5=self.md5,
            assembly="FAIL",
        )
        study.mandatory_metadata_check()
        self.assertEqual(study.error_code, 5)

    def test_validate_study_invalid_file_path(self):
        study = st.Study(
            study_id=self.study_id,
            file_path=self.file_path,
            md5=self.md5,
            assembly=self.assembly,
            callback_id="1234abcd",
            entryUUID=self.entryUUID,
        )
        study.retrieve_study_file()
        self.assertEqual(study.error_code, 1)

    def test_validate_study_md5_invalid(self):
        study = st.Study(
            study_id=self.study_id,
            file_path=self.valid_file,
            md5=self.md5,
            assembly=self.assembly,
            callback_id="1234abcd",
            entryUUID=self.entryUUID,
        )
        study.retrieve_study_file()
        study.validate_study()
        self.assertEqual(study.error_code, 2)

    def test_validate_valid_study(self):
        study = st.Study(
            study_id=self.study_id,
            file_path=self.valid_file,
            md5=self.valid_file_md5,
            assembly=self.assembly,
            callback_id=self.callback_id,
            entryUUID=self.entryUUID,
        )
        study.retrieve_study_file()
        study.validate_study(minrows=2)
        self.assertEqual(study.data_valid, 1)

    def test_validate_study_not_enough_rows(self):
        study = st.Study(
            study_id=self.study_id,
            file_path=self.valid_file,
            md5=self.valid_file_md5,
            assembly=self.assembly,
            callback_id=self.callback_id,
            entryUUID=self.entryUUID,
        )
        study.retrieve_study_file()
        study.validate_study(minrows=100)
        self.assertEqual(study.data_valid, 0)
        self.assertEqual(study.error_code, 9)

    def test_validate_invalid_study_zero_p_values(self):
        study = st.Study(
            study_id=self.study_id,
            file_path=self.file_zero_p_values,
            md5=self.md5_file_zero_p_values,
            assembly=self.assembly,
            callback_id=self.callback_id,
            entryUUID=self.entryUUID,
        )
        study.retrieve_study_file()
        study.validate_study(minrows=2, zero_p_values=False)
        self.assertEqual(study.data_valid, 0)
        self.assertEqual(study.error_code, 12)


if __name__ == "__main__":
    unittest.main()
