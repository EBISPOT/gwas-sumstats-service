import os
import urllib
import config
import hashlib
import logging
import validate.validator as val
import pathlib


logging.basicConfig(level=logging.INFO, format='(%(levelname)s): %(message)s')
logger = logging.getLogger(__name__)


class SumStatFile:
    def __init__(self, file_path=None, callback_id=None, study_id=None, md5exp=None):
        self.file_path = file_path
        self.callback_id = callback_id
        self.study_id = study_id
        self.md5exp = md5exp
        self.logfile = None

    def set_logfile(self):
        self.logfile = os.path.join(self.parent_path, str(self.study_id + ".log"))
        handler = logging.FileHandler(self.logfile)
        handler.setLevel(logging.ERROR)
        logger.addHandler(handler)

    def make_parent_dir(self):
        try:
            self.set_parent_path()
            os.makedirs(self.parent_path)
        except FileExistsError:
            pass

    def retrieve(self):
        logger.info("Fetching file from URL: {}".format(self.file_path))        
        self.make_parent_dir()
        self.ext = self.get_ext()
        logger.debug("File extension: {}".format(self.ext))        
        if self.ext:
            self.set_store_path()
        try:
            urllib.request.urlretrieve(self.file_path, self.store_path)
            logger.debug("File written: {}".format(self.store_path))        
            return True
        except urllib.error.URLError as e:
            print(e)
        except ValueError as e:
            print(e)
        return False

    def set_parent_path(self):
        self.parent_path = os.path.join(config.STORAGE_PATH, self.callback_id)

    def set_store_path(self):
        if self.study_id: 
               self.store_path = os.path.join(self.parent_path, str(self.study_id + self.ext))

    def get_store_path(self):
        self.get_ext()
        self.set_store_path()
        return self.store_path

    def md5_ok(self):
        f = self.get_store_path()
        if self.md5exp == md5_check(f):
            return True
        return False

    def get_ext(self):
        ext = pathlib.Path(self.file_path).suffix
        return ext if ext else False


    def validate_file(self):
        validator = val.Validator(file=self.store_path, filetype='standard')
        self.set_logfile()
        logger.info("Validating file extension...")
        if not validator.validate_file_extenstion():
            return False
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

