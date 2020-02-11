import os
import urllib
from urllib.parse import urlparse, parse_qs, urlunparse
import requests
import gzip
import shutil
import config
import hashlib
import magic
import csv
import logging
import validate.validator as val
import pathlib
from sumstats_service.resources.error_classes import *
import ftplib


logging.basicConfig(level=logging.DEBUG, format='(%(levelname)s): %(message)s')
logger = logging.getLogger(__name__)


class SumStatFile:
    def __init__(self, file_path=None, callback_id=None, study_id=None, 
                md5exp=None, readme=None, entryUUID=None,
                staging_dir_name=None, staging_file_name=None):
        self.file_path = file_path
        self.callback_id = callback_id
        self.study_id = study_id
        self.md5exp = md5exp
        self.logfile = None
        self.readme = readme
        self.entryUUID = entryUUID
        self.staging_dir_name = staging_dir_name
        self.staging_file_name = staging_file_name


    def set_logfile(self):
        for handler in logger.handlers[:]:  # remove all old handlers
            logger.removeHandler(handler)
        self.logfile = os.path.join(self.parent_path, str(self.study_id + ".log"))
        handler = logging.FileHandler(self.logfile)
        handler.setLevel(logging.INFO)
        logger.addHandler(handler)

    def make_parent_dir(self):
        try:
            self.set_parent_path()
            os.makedirs(self.parent_path)
        except FileExistsError:
            pass

    def retrieve(self):
        download_status = False
        self.make_parent_dir()
        self.set_store_path()

        # if Globus uploaded:
        if self.entryUUID:
            logger.debug("Fetching file {} from ftp, parent path: {}".format(self.file_path, self.entryUUID))  
            source_path = os.path.join(self.entryUUID, self.file_path)
            download_status = download_from_ftp(server=config.FTP_SERVER, user=config.FTP_USERNAME, password=config.FTP_PASSWORD, source=source_path, dest=self.store_path)

        # else check to see if URL we can use
        else:
            try:
                logger.debug("Fetching file from URL: {}".format(self.file_path))        
                url_parts = parse_url(self.file_path)
                if url_parts is False:
                    return False
                # check if gdrive
                logger.debug(get_net_loc(self.file_path))
                if "drive.google" in get_net_loc(self.file_path):
                    logger.debug("gdrive file")
                    download_status = self.download_from_gdrive()
                elif "dropbox" in  get_net_loc(self.file_path):
                    logger.debug("dropbox file")
                    download_status = self.download_from_dropbox()
                elif "http" in url_parts.scheme:
                    logger.debug("http download")
                    download_status = download_with_requests(self.file_path, self.store_path)
                else:
                    logger.debug("not http download")
                    download_status = download_with_urllib(self.file_path, self.store_path)
            except Exception as e:
                logger.error(e)
                return False

        if download_status == True:
            ext = self.get_ext()
            path_with_ext = self.store_path + ext
            os.rename(self.store_path, path_with_ext)
            self.store_path =  path_with_ext
            logger.debug("store path is {}".format(self.store_path))
        return download_status # True or False

    def set_parent_path(self):
        self.parent_path = os.path.join(config.STORAGE_PATH, self.callback_id)

    def set_store_path(self):
        if self.study_id: 
               self.store_path = os.path.join(self.parent_path, str(self.study_id))

    def download_from_dropbox(self):
        url = self.file_path
        url_parse = parse_url(url)
        if url_parse.query:
            download_true_query = url_parse.query.replace("dl=0", "dl=1")
            url = urlunparse(url_parse._replace(query=download_true_query))
        return download_with_requests(url, self.store_path)

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
            ext = self.get_ext()
            path_with_ext = self.store_path + ext
            self.store_path =  path_with_ext
        return self.store_path

    def write_readme_file(self):
        if self.readme:
            readme_path = os.path.join(self.parent_path, str(self.study_id)) + ".README"
            with open(readme_path, 'w') as readme:
                readme.write(self.readme)

    def md5_ok(self):
        f = self.get_store_path()
        logger.info("md5: " + md5_check(f))
        if self.md5exp == md5_check(f):
            return True
        return False

    def get_ext(self):
        ext = None
        detect = magic.Magic(uncompress=True)
        description = detect.from_file(self.store_path)
        logger.info("file type description: " + description)
        if "gzip" in description:
            with gzip.open(self.store_path, 'rt') as f:
                ext = self.get_dialect(f) + ".gz"
        else:
            with open(self.store_path, 'r') as f:
                ext = self.get_dialect(f)
        return ext

    def validate_file(self):
        self.set_logfile()
        validator = val.Validator(file=self.store_path, filetype='standard', error_limit=1, logfile=self.logfile)
        try:
            logger.info("Validating file extension...")
            if not validator.validate_file_extension():
                logger.info("VALIDATION FAILED")
                return False
            logger.info("Validating headers...")
            if not validator.validate_headers():
                logger.info("Invalid headers...exiting before any further checks")
                logger.info("VALIDATION FAILED")
                return False
            logger.info("Validating data...")
            if validator.validate_data():
                logger.info("VALIDATION SUCCESSFUL")
                return True
            else:
                logger.info("VALIDATION FAILED")
                return False
        except Exception as e:
            logger.error(e)
            logger.info("VALIDATION FAILED")
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


    def move_file_to_staging(self):
        self.set_parent_path()
        self.set_store_path()
        file_ext = self.get_ext()
        source_file = self.store_path + file_ext
        source_readme =  os.path.join(self.parent_path, str(self.study_id)) + ".README"
        dest_dir = os.path.join(config.STAGING_PATH, self.staging_dir_name)
        dest_file = os.path.join(dest_dir, self.staging_file_name) + file_ext
        dest_readme = os.path.join(dest_dir, "README.txt") 
        try:
            os.makedirs(dest_dir)
        except FileExistsError:
            pass
        os.rename(source_file, dest_file)
        os.rename(source_readme, dest_readme)
        return True




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

def parse_url(url):
    url_parse = urlparse(url)
    if not url_parse.scheme:
        logger.error("No schema defined in URL")
        return False
    else:
        return url_parse

def download_with_urllib(url, localpath):
    try:
        urllib.request.urlretrieve(url, localpath)
        logger.debug("File written: {}".format(url))        
        return True
    except urllib.error.URLError as e:
        logger.error(e)
    except ValueError as e:
        logger.error(e)
    return False

def download_with_requests(url, localpath):
    response = requests.head(url)
    if response.status_code != 200:
        logger.error("URL status code: {}".format(response.status_code))
        return False
    else:
        try:
            # stream prevents us from running into memory issues
            with requests.get(url, stream=True) as r:
                # for handling gzip/non-gzipped
                r.raw.decode_content = True 
                with open(localpath, 'wb') as f:
                    shutil.copyfileobj(r.raw, f)
                    logger.debug("File written: {}".format(url))        
                    return True
        except requests.exceptions.RequestException as e:
            logger.error(e)
            return False


def get_net_loc(url):
    return urlparse(url).netloc


def get_gdrive_id(url):
    file_id = None
    url_parse = parse_url(url)
    if url_parse.query and "id" in parse_qs(url_parse.query):
        file_id = parse_qs(url_parse.query)["id"]
    else:
        try:
            file_id = url_parse.path.split("/d/")[1].split("/")[0]
        except IndexError:
            logger.error("Couldn't parse id from url path: {}".format(url_parse.path))
    if not file_id:
        logger.error("Gdrive URL given but no id given")
    return file_id


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


def download_from_ftp(server, user, password, source, dest):
    try:
        ftp = ftplib.FTP(server)
        ftp.login(user, password)
        if ftp.nlst(source):
            with open(dest, "wb") as f:
                ftp.retrbinary("RETR " + source, f.write)
                ftp.quit()
                return True
        else:
            logger.error("couldn't find {}".format(source))
            ftp.quit()
            return False
    except ftplib.all_errors as e:
            logger.error(e)
            return False

    
