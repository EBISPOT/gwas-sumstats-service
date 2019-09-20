import os
import urllib
from urllib.parse import urlparse, parse_qs
import requests
import gzip
import gdown
import shutil
import config
import hashlib
import magic
import csv
import logging
import validate.validator as val
import pathlib
from sumstats_service.resources.error_classes import *


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
        self.set_store_path()
        # check if gdrive
        logger.debug(get_net_loc(self.file_path))
        if "drive.google.com" in get_net_loc(self.file_path) :
            logger.info("gdrive file")
            download_status = self.download_from_gdrive()
        # elif dropbox
        else:
            logger.info("standard file path")
            download_status = self.download_with_urllib()
        if download_status == True:
            ext = self.get_ext()
            path_with_ext = self.store_path + ext
            os.rename(self.store_path, path_with_ext)
            self.store_path =  path_with_ext
            logger.info("store path is {}".format(self.store_path))
        return download_status # True or False

    def set_parent_path(self):
        self.parent_path = os.path.join(config.STORAGE_PATH, self.callback_id)

    def set_store_path(self):
        if self.study_id: 
               self.store_path = os.path.join(self.parent_path, str(self.study_id))

    def download_with_urllib(self):
        try:
            urllib.request.urlretrieve(self.file_path, self.store_path)
            logger.debug("File written: {}".format(self.store_path))        
            return True
        except urllib.error.URLError as e:
            logger.error(e)
        except ValueError as e:
            logger.error(e)
        return False

    def download_from_gdrive(self):
        file_id = get_gdrive_id(self.file_path)
        if file_id:
            try:
                download_file_from_google_drive(file_id, self.store_path)
                return True
            except requests.exceptions.RequestException as e:
                logger.error(e)
        return False

    def get_store_path(self):
        if not self.store_path:
            self.set_store_path()
            self.get_ext()
            path_with_ext = self.store_path + ext
            self.store_path =  path_with_ext
        return self.store_path

    def md5_ok(self):
        f = self.get_store_path()
        if self.md5exp == md5_check(f):
            return True
        return False

    def get_ext(self):
        ext = None
        detect = magic.Magic(uncompress=True)
        description = detect.from_file(self.store_path)
        if "gzip" in description:
            with gzip.open(self.store_path, 'rt') as f:
                ext = self.get_dialect(f) + ".gz"
        else:
            with open(self.store_path, 'r') as f:
                ext = self.get_dialect(f)
        return ext

    def validate_file(self):
        validator = val.Validator(file=self.store_path, filetype='standard')
        self.set_logfile()
        logger.info("Validating file extension...")
        if not validator.validate_file_extension():
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


    def get_dialect(self, csv_file):
        detect = csv.Sniffer().sniff(csv_file.readline()).delimiter
        if str(detect) == '\t':
            return ".tsv"
        elif str(detect) == ',':
            return ".csv"
        else:
            ext = pathlib.Path(self.file_path).suffix
            if ext:
                return ext
            else:
                logger.error("Unable to determine file type/extension setting to .tsv")
                return ".tsv"


def md5_check(file):
    hash_md5 = hashlib.md5()
    with open(file, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def remove_payload(callback_id):
    path = os.path.join(config.STORAGE_PATH, callback_id)
    try:
        shutil.rmtree(path)
    except FileNotFoundError as e:
        logger.error(e)


def get_net_loc(url):
    return urlparse(url).netloc

def get_gdrive_id(url):
    queries = parse_qs(urlparse(url).query)
    try:
        file_id = queries["id"]
        return file_id
    except KeyError:
        logger.error("Gdrive URL given but no id given")
        return False
    ## USE gdown

def download_file_from_google_drive(id, destination):
    def get_confirm_token(response):
        for key, value in response.cookies.items():
            if key.startswith('download_warning'):
                return value
        return None

    def save_response_content(response, destination):
        CHUNK_SIZE = 32768
        with open(destination, "wb") as f:
            for chunk in response.iter_content(CHUNK_SIZE):
                if chunk: # filter out keep-alive new chunks
                    f.write(chunk)

    URL = "https://docs.google.com/uc?export=download"
    session = requests.Session()
    response = session.get(URL, params = { 'id' : id }, stream = True)
    token = get_confirm_token(response)
    if token:
        params = { 'id' : id, 'confirm' : token }
        response = session.get(URL, params = params, stream = True)
    save_response_content(response, destination)
    
