import unittest
import os
import shutil
from sumstats_service import config
import sumstats_service.resources.file_handler as fh


class TestSumStatsFile(unittest.TestCase):
    def setUp(self):
        self.test_storepath = "./tests/data"
        config.STORAGE_PATH = self.test_storepath
        config.BROKER_PORT = 5682
        config.BROKER_HOST = "localhost"
        config.DEPO_PATH = './tests'
        self.cid = "TiQS2yxVa"
        self.sid = "mKoYvoLH8L"
        self.entryUUID = "ABC1234"
        self.valid_file = "test_sumstats_file.tsv"
        self.valid_file_md5 = "a1195761f082f8cbc2f5a560743077cc"
        os.makedirs(config.STORAGE_PATH, exist_ok=True)
        self.test_validate_path = os.path.join(config.VALIDATED_PATH, self.cid)
        os.makedirs(self.test_validate_path, exist_ok=True)
        self.invalid_file = "test_invalid.tsv"


    def tearDown(self):
        shutil.rmtree(self.test_storepath)
        shutil.rmtree(self.test_validate_path)

    def test_make_parent_dir(self):
        ssf = fh.SumStatFile(callback_id=self.cid, study_id=self.sid)
        ssf.set_parent_path()
        self.assertFalse(os.path.exists(ssf.parent_path))
        ssf.make_parent_dir()
        self.assertTrue(os.path.exists(ssf.parent_path))

    def test_remove_parent_dir(self):
        ssf = fh.SumStatFile(callback_id=self.cid, study_id=self.sid)
        ssf.set_parent_path()
        self.assertFalse(os.path.exists(ssf.parent_path))
        ssf.make_parent_dir()
        self.assertTrue(os.path.exists(ssf.parent_path))
        fh.remove_payload(self.cid)
        self.assertFalse(os.path.exists(ssf.parent_path))

    def test_retrieve(self):
        ssf = fh.SumStatFile(file_path=self.valid_file, callback_id=self.cid, study_id=self.sid, entryUUID=self.entryUUID)
        retrieved = ssf.retrieve()
        self.assertTrue(retrieved)

    def test_md5(self):
        ssf = fh.SumStatFile(file_path=self.valid_file, callback_id=self.cid,
                study_id=self.sid, md5exp=self.valid_file_md5, entryUUID=self.entryUUID)
        ssf.retrieve()
        self.assertEqual(fh.md5_check(os.path.join(ssf.store_path)),self.valid_file_md5)
        md5_ok = ssf.md5_ok()
        self.assertTrue(md5_ok)

    def test_validate_true_when_valid(self):        
        ssf = fh.SumStatFile(file_path=self.valid_file, callback_id=self.cid,
                study_id=self.sid, md5exp=self.valid_file_md5, minrows=10, entryUUID=self.entryUUID)
        ssf.retrieve()
        result = ssf.validate_file()
        self.assertTrue(result)
        self.assertTrue(os.path.exists(os.path.join(ssf.get_valid_parent_path(), str(self.sid + ".log"))))

    def test_validate_false_when_invalid(self):
        ssf = fh.SumStatFile(file_path=self.invalid_file, callback_id=self.cid,
                study_id=self.sid, md5exp=self.valid_file_md5, minrows=10, entryUUID=self.entryUUID)
        ssf.retrieve()
        result = ssf.validate_file()
        self.assertFalse(result)
        self.assertTrue(os.path.exists(os.path.join(ssf.get_valid_parent_path(), str(self.sid + ".log"))))




