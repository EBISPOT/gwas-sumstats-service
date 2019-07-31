import unittest
import os
import shutil
import config
import helpers.file_handler as fh


class TestSumStatsFile(unittest.TestCase):
    def setUp(self):
        self.test_storepath = "./tests/data"
        config.STORAGE_PATH = self.test_storepath
        self.cid = "TiQS2yxV"
        self.sid = "mKoYvoLH8L"

    def tearDown(self):
        shutil.rmtree(self.test_storepath)

    def test_make_parent_dir(self):
        ssf = fh.SumStatFile(callback_id=self.cid, study_id=self.sid)
        self.assertFalse(os.path.exists(ssf.parent_path))
        ssf.make_parent_dir()
        self.assertTrue(os.path.exists(ssf.parent_path))



