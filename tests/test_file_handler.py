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

    def tearDown(self):
        shutil.rmtree(self.test_storepath)

    def test_make_parent_dir(self):
        ssf = fh.SumStatFile(callback_id=self.cid)
        self.assertFalse(os.path.exists(ssf.store_path))
        ssf.make_parent_dir()
        self.assertTrue(os.path.exists(ssf.store_path))



