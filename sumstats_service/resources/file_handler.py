import os
from glob import glob
import urllib
from urllib.parse import urlparse
import requests
import gzip
import shutil
from sumstats_service import config
import hashlib
import magic
import csv
import io
import logging
import validate.validator as val
import pathlib
import sumstats_service.resources.globus as globus
from sumstats_service.resources.convert_meta import MetadataConverter


logging.basicConfig(level=logging.DEBUG, format='(%(levelname)s): %(message)s')
logger = logging.getLogger(__name__)


class SumStatFile:
    def __init__(self, file_path=None, callback_id=None, study_id=None, 
                md5exp=None, readme=None, entryUUID=None,
                staging_dir_name=None, staging_file_name=None, minrows=None,
                raw_ss=None, uploaded_ss_filename=None):
        self.file_path = file_path
        self.callback_id = callback_id
        self.study_id = study_id
        self.md5exp = md5exp
        self.logfile = None
        self.readme = readme
        self.entryUUID = entryUUID
        self.staging_dir_name = staging_dir_name
        self.staging_file_name = staging_file_name
        self.minrows = minrows
        self.raw_ss = raw_ss
        self.uploaded_ss_filename = uploaded_ss_filename
        self.store_path = None
        self.parent_path = None


    def set_logfile(self):
        for handler in logger.handlers[:]:  # remove all old handlers
            logger.removeHandler(handler)
        self.logfile = os.path.join(self.get_valid_parent_path(), str(self.study_id + ".log"))
        handler = logging.FileHandler(self.logfile)
        handler.setLevel(logging.INFO)
        logger.addHandler(handler)

    def make_parent_dir(self):
        try:
            self.set_parent_path()
            os.makedirs(self.parent_path)
        except FileExistsError:
            pass

    def check_raw_ss(self):
        if self.raw_ss:
            source_path = os.path.join(self.entryUUID, self.raw_ss)
            raw_ss_exists = filepath_exists_with_globus(source_path)
            return raw_ss_exists
        return True

    def retrieve(self):
        self.make_parent_dir()
        self.set_store_path()
        source_path = self._get_source_file()
        # copy from source_path to store_path
        try:
            shutil.copyfile(source_path, self.store_path)
            return True
        except FileNotFoundError:
            logger.error(f"Could not find {source_path}")
            return False

    def _get_source_dir(self):
        return os.path.join(config.DEPO_PATH, self.entryUUID)

    def _get_source_file(self):
        return os.path.join(self._get_source_dir(), self.file_path)

    def set_parent_path(self):
        logger.debug(config.STORAGE_PATH)
        logger.debug(self.callback_id)
        self.parent_path = os.path.join(config.STORAGE_PATH, self.callback_id)

    def set_store_path(self):
        if self.study_id:
            if not self.parent_path:
                self.set_parent_path()
            self.store_path = os.path.join(self.parent_path, str(self.study_id))

    def get_valid_parent_path(self):
        if self.study_id: 
            self.valid_parent_path = os.path.join(config.VALIDATED_PATH, self.callback_id)
            return self.valid_parent_path


    def set_valid_path(self):
        if self.study_id: 
               self.valid_path = os.path.join(self.valid_parent_path, str(self.study_id))

    def get_store_path(self):
        if not self.store_path:
            self.set_store_path()
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

    def rename_file_with_ext(self):
        ext = self.get_ext()
        path_with_ext = self.store_path + ext
        os.rename(self.store_path, path_with_ext)
        self.store_path = path_with_ext
        logger.info(self.store_path)

    def validate_file(self):
        self.rename_file_with_ext()
        self.set_logfile()
        self.validation_error = 3
        if self.minrows:
            validator = val.Validator(file=self.store_path, filetype='gwas-upload', error_limit=1, logfile=self.logfile, minrows=self.minrows)
        else:
            validator = val.Validator(file=self.store_path, filetype='gwas-upload', error_limit=1, logfile=self.logfile)
        try:
            logger.info("Validating file extension...")
            if not validator.validate_file_extension():
                logger.info("VALIDATION FAILED")
                self.validation_error = 6
                return False
            logger.info("Validating headers...")
            if not validator.validate_headers():
                logger.info("Invalid headers...exiting before any further checks")
                logger.info("VALIDATION FAILED")
                self.validation_error = 7
                return False

            logger.info("Validating file for squareness...")
            if not validator.validate_file_squareness():
                logger.info("Rows are malformed..exiting before any further checks")
                self.validation_error = 8
                return False

            logger.info("Validating rows...")
            if not validator.validate_rows():
                logger.info("File contains too few rows..exiting before any further checks")
                self.validation_error = 9
                return False

            logger.info("Validating data...")
            if validator.validate_data():
                logger.info("VALIDATION SUCCESSFUL")
                return True
            else:
                logger.info("VALIDATION FAILED")
                self.validation_error = 3
                return False

        except Exception as e:
            logger.error(e)
            logger.info("VALIDATION FAILED")
            return False


    def get_dialect(self, csv_file):
        try:
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
        except Exception as e:
            logger.error(e)
            logger.error("Guessing extension, setting to .tsv")
            return ".tsv"


    def write_metadata_file(self, input_metadata, dest_file):
        data_file = pathlib.Path(dest_file).name
        metadata_converter = MetadataConverter(accession_id=self.staging_file_name,
                                  md5sum=self.md5exp,
                                  in_file=input_metadata,
                                  out_file=dest_file + "-meta.yaml",
                                  schema="schema/meta_schema.yaml",
                                  data_file=data_file
                                  )
        return metadata_converter.convert_to_outfile()

    def convert_metadata_to_yaml(self, dest_file):
        template = self.get_template()
        if template is None:
            raise ValueError(f"No template found for {self.callback_id}")
        else:
            with io.BytesIO(template) as fh:
                self.write_metadata_file(input_metadata=fh, dest_file=dest_file)


    def move_file_to_staging(self):
        """
        TODO: move raw ss if needed
        """
        try:
            source_dir = os.path.join(config.STORAGE_PATH, self.callback_id)
            source_file_without_ext = os.path.join(source_dir, self.study_id)
            source_file = add_ext_to_file_without_ext(source_file_without_ext)
            dest_dir = os.path.join(config.STAGING_PATH, self.staging_dir_name)
            ext = get_ext_for_file(file_path=source_file)
            dest_file = os.path.join(dest_dir, self.staging_file_name + ext)
            pathlib.Path(dest_dir).mkdir(parents=True, exist_ok=True)
            shutil.move(source_file, dest_file)
            self.convert_metadata_to_yaml(dest_file)
        except (IndexError, FileNotFoundError, OSError) as e:
            raise IOError("Error: {}\nCould not move file {} to staging,\ "
                         "callback ID: {}".format(e,
                                                  self.staging_file_name,
                                                  self.callback_id))
        return True

    def get_template(self):
        """
        Get template or None
        download template
        :param self: 
        :return: bytes or None
        """
        url = urllib.parse.urljoin(config.GWAS_DEPO_REST_API_URL, "submissions/uploads")
        params = {"callbackId": self.callback_id}
        headers = {"jwt": config.DEPO_API_AUTH_TOKEN}
        return download_with_requests(url=url, params=params, headers=headers)


def get_ext_for_file(file_path):
    """
    Get the full extension for a file path
    :param file_path:
    :return: extension
    """
    suffixes = pathlib.Path(file_path).suffixes
    ext = "".join(suffixes)
    return ext

def add_ext_to_file_without_ext(file_without_ext):
    """
    Add the extension to the file name.
    There will only be one glob match for the file without ext.
    :param file_without_ext:
    :return: file with ext
    """
    matching_files = glob(file_without_ext + '*')
    if len(matching_files) != 1:
        raise ValueError(f"Could not find one and only one matching file for {file_without_ext}")
    else:
        return matching_files[0]


def get_source_file_from_id(source_dir, source):
    files = globus.list_files(source_dir)
    source_with_ext = None
    ext = None
    filter_files = [f for f in [f for f in files if not ".README" in f] if not ".log" in f]
    if filter_files:
        for f in filter_files:
            file_ext = "".join(pathlib.Path(f).suffixes)
            file_no_ext = f.replace(file_ext, "")
            logger.debug("source: {}, file: {}".format(source, f))
            if source == file_no_ext:
                source_with_ext = f
                ext = file_ext
                break
    return (source_with_ext, ext)


def mv_file_with_globus(dest_dir, source, dest):
    #create the new dir
    try:
        globus.mkdir(unique_id=dest_dir)
    except:
        pass
    status = globus.rename_file(dest_dir, source, dest)
    return status

def filepath_exists_with_globus(path):
    return globus.filepath_exists(path)

def md5_check(file):
    hash_md5 = hashlib.md5()
    with open(file, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def remove_payload(callback_id):
    path = os.path.join(config.STORAGE_PATH, callback_id)
    try:
        shutil.rmtree(path, ignore_errors=True)
    except FileNotFoundError as e:
        logger.error(e)


def remove_payload_validated_files(callback_id):
    path_to_remove = os.path.join(config.VALIDATED_PATH, callback_id)
    logger.info("remove path: {}".format(path_to_remove))
    status = globus.remove_path(path_to_remove)
    logger.info(status)    
    return status


def parse_url(url):
    url_parse = urlparse(url)
    if not url_parse.scheme:
        logger.error("No schema defined in URL")
        return False
    else:
        return url_parse


def download_with_requests(url, params=None, headers=None):
    """
    Return content from URL if status code is 200
    :param url: 
    :param headers: 
    :return: content in bytes or None
    """
    try:
        with requests.get(url, params=params, headers=headers) as r:
            status_code = r.status_code
            if status_code != 200:
                logger.error(f"{url} returned {status_code} status code")
                return None
            else:
                return r.content
    except requests.exceptions.RequestException as e:
        logger.error(e)
        return None
