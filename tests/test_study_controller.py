import unittest
import os
import config
from resources.sqlite_client import sqlClient
import resources.study_controller as sc


class TestStudyController(unittest.TestCase):
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
        study = sc.Study(study_id=study_id, pmid=pmid, file_path=file_path, md5=md5, assembly=assembly)
        self.assertTrue(study.valid_study_id())
        # invalid study id
        study_id = "asd1232 asd"
        study = sc.Study(study_id=study_id, pmid=pmid, file_path=file_path, md5=md5, assembly=assembly)
        self.assertFalse(study.valid_study_id())


    def test_study_id_exists_in_db(self):
        pass





if __name__ == '__main__':
    unittest.main()
