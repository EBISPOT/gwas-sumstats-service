import os
import requests
import config
import hashlib
import logging
import validate.validator as val


logging.basicConfig(level=logging.INFO, format='(%(levelname)s): %(message)s')
logger = logging.getLogger(__name__)

class SumStatFile:
    def __init__(self, file_path=None, callback_id=None, study_id=None, md5exp=None):
        self.file_path = file_path
        self.callback_id = callback_id
        self.study_id = study_id
        self.md5exp = md5exp
        if callback_id:
            self.parent_path = os.path.join(config.STORAGE_PATH, self.callback_id)
            if study_id: 
                self.store_path = os.path.join(self.parent_path, self.study_id)
        self.logfile = None

    def set_logfile(self):
        self.logfile = os.path.join(self.parent_path, str(self.study_id + ".log"))
        handler = logging.FileHandler(self.logfile)
        handler.setLevel(logging.ERROR)
        logger.addHandler(handler)

    def make_parent_dir(self):
        try:
            os.makedirs(self.parent_path)
        except FileExistsError:
            pass

    def retrieve(self):
        self.make_parent_dir()
        try:
            response = requests.get(self.file_path)
        except requests.exceptions.RequestException as e:
            print(e)
            return False
        if response.status_code == 200:
            with open(self.store_path, 'wb') as f:
                f.write(response.content)
                return True
        else:
            return False

    def md5_ok(self):
        if self.md5exp == md5_check(self.store_path):
            return True
        return False

    def validate_file(self):
        validator = val.Validator(file=self.store_path, stage='standard')
        self.set_logfile()
        logger.info("Validating headers...")
        if not validator.validate_headers():
            logger.info("Invalid headers...exiting before any further checks")
            return False
        logger.info("Validating data...")
        if validator.validate_data():
            return True
        else:
            return False

def md5_check(file):
    hash_md5 = hashlib.md5()
    with open(file, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()
        

