import unittest
import os
import shutil
import config
import sumstats_service.resources.file_handler as fh


class TestSumStatsFile(unittest.TestCase):
    def setUp(self):
        self.test_storepath = "./tests/data"
        config.STORAGE_PATH = self.test_storepath
        self.cid = "TiQS2yxV"
        self.sid = "mKoYvoLH8L"
        self.valid_url = "https://raw.githubusercontent.com/EBISPOT/gwas-sumstats-service/master/tests/test_sumstats_file.tsv"
        self.valid_url_md5 = "a1195761f082f8cbc2f5a560743077cc"

    def tearDown(self):
        shutil.rmtree(self.test_storepath)

    def test_make_parent_dir(self):
        ssf = fh.SumStatFile(callback_id=self.cid, study_id=self.sid)
        self.assertFalse(os.path.exists(ssf.parent_path))
        ssf.make_parent_dir()
        self.assertTrue(os.path.exists(ssf.parent_path))

    def test_retrieve(self):
        ssf = fh.SumStatFile(file_path=self.valid_url, callback_id=self.cid, study_id=self.sid)
        retrieved = ssf.retrieve()
        self.assertTrue(retrieved)
        self.assertTrue(os.path.exists(os.path.join(ssf.parent_path, self.sid)))
        
    def test_md5(self):
        ssf = fh.SumStatFile(file_path=self.valid_url, callback_id=self.cid, 
                study_id=self.sid, md5exp=self.valid_url_md5)
        ssf.retrieve()
        self.assertEqual(fh.md5_check(os.path.join(ssf.parent_path, self.sid)),self.valid_url_md5)
        md5_ok = ssf.md5_ok()
        self.assertTrue(md5_ok)






