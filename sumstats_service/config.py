import os


def _env_variable_else(env_var_name, default):
    return os.environ.get(env_var_name) if os.environ.get(env_var_name) else default

DB_PATH = "./data/sumstats_meta.db"
STORAGE_PATH = _env_variable_else('STORAGE_PATH', './data')
LOGGING_PATH = "../logs"
STAGING_PATH = _env_variable_else('STAGING_PATH', 'depo_ss_staging')
VALIDATED_PATH = _env_variable_else('VALIDATED_PATH', 'depo_ss_validated')
SW_PATH = _env_variable_else('SW_PATH', './bin')
DEPO_PATH = _env_variable_else('DEPO_PATH', './depo_data')
CONTAINERISE = _env_variable_else('CONTAINERISE', './depo_data')


# --- Rabbit and Celery --- #

BROKER = "amqp"
BROKER_HOST = "rabbitmq"
BROKER_PORT = 5672
# the following two queues were required for EHK + EBI LSF cluster
# install (pre-validation and post-validation) but are not required
# if the worker is able to perform validation and see the database
CELERY_QUEUE1 = _env_variable_else('CELERY_QUEUE1', 'preval')
CELERY_QUEUE2 = _env_variable_else('CELERY_QUEUE2', 'postval')

# --- Remote --- #

VALIDATE_WITH_SSH = _env_variable_else('VALIDATE_WITH_SSH', False)
COMPUTE_FARM_LOGIN_NODE = _env_variable_else('COMPUTE_FARM_LOGIN_NODE', None)
COMPUTE_FARM_USERNAME = _env_variable_else('COMPUTE_FARM_USERNAME', None)
COMPUTE_FARM_QUEUE = 'production'
COMPUTE_FARM_QUEUE_LONG = _env_variable_else('COMPUTE_FARM_QUEUE_LONG', 'production')
REMOTE_HTTP_PROXY = _env_variable_else('REMOTE_HTTP_PROXY', None)
REMOTE_HTTPS_PROXY = _env_variable_else('REMOTE_HTTPS_PROXY', None)
SINGULARITY_IMAGE = _env_variable_else('SINGULARITY_IMAGE', 'ebispot/gwas-sumstats-service')
SINGULARITY_TAG = _env_variable_else('SINGULARITY_TAG', 'latest')

# --- MONGO DB --- #

MONGO_URI = _env_variable_else('MONGO_URI', None)
MONGO_USER = _env_variable_else('MONGO_USER', '')
MONGO_PASSWORD = _env_variable_else('MONGO_PASSWORD', '')
MONGO_DB = _env_variable_else('MONGO_DB', None)


# --- File transfer (FTP nad Globus) config --- #

FTP_SERVER = _env_variable_else('FTP_SERVER', None)
FTP_USERNAME =  _env_variable_else('FTP_USERNAME', None)
FTP_PASSWORD = _env_variable_else('FTP_PASSWORD', None)

TOKEN_FILE = 'refresh-tokens.json'
REDIRECT_URI = 'https://auth.globus.org/v2/web/auth-code'
SCOPES = ('openid email profile '
          'urn:globus:auth:scope:transfer.api.globus.org:all')
GWAS_ENDPOINT_ID = _env_variable_else('GWAS_ENDPOINT_ID', None)
GLOBUS_SECRET = _env_variable_else('GLOBUS_SECRET', None)
CLIENT_ID = _env_variable_else('CLIENT_ID', None)
TRANSFER_CLIENT_ID = _env_variable_else('TRANSFER_CLIENT_ID', None)
GWAS_GLOBUS_GROUP = _env_variable_else('GWAS_GLOBUS_GROUP', None)
DEPO_API_AUTH_TOKEN = _env_variable_else('DEPO_API_AUTH_TOKEN', None)
OUTPUT_PATH = _env_variable_else('OUTPUT_PATH', 'metadata/output')

# --- SQLite schema --- # 

DB_SCHEMA = """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS studies (
            studyID TEXT NOT NULL UNIQUE,
            callbackID TEXT,
            filePath TEXT,
            md5 TEXT,
            assembly TEXT,
            retrieved INT CHECK (retrieved IN (0,1)),
            dataValid INT CHECK (dataValid IN (0,1)),
            errorCode INT,
            readme TEXT,
            entryUUID TEXT,
            FOREIGN KEY(errorCode) REFERENCES errors(id)
            );

            CREATE TABLE IF NOT EXISTS errors (
            id INTEGER PRIMARY KEY,
            errorText TEXT UNIQUE
            );

            BEGIN TRANSACTION;
            INSERT OR IGNORE INTO errors(id, errorText) VALUES(1, "The summary statistics file cannot be found"); -- 1
            INSERT OR IGNORE INTO errors(id, errorText) VALUES(2, "The md5sum of the summary statistics file does not match the one provided"); -- 2
            INSERT OR IGNORE INTO errors(id, errorText) VALUES(3, "Summary statistics file validation failed, please run the validator on your file to see the errors (available here: https://pypi.org/project/ss-validate/)"); -- 3
            INSERT OR IGNORE INTO errors(id, errorText) VALUES(4, "Missing mandatory field, you must provide (i) file path/URL, (ii) md5 sum and (iii) genome assembly for each file"); -- 4
            INSERT OR IGNORE INTO errors(id, errorText) VALUES(5, "Genome assembly invalid - please see documentation for valid assemblies"); -- 5 
            COMMIT;
            """

VALIDATION_ERRORS = [
                        {'id': 1, 'errorText': 'The summary statistics file cannot be found'},
                        {'id': 2, 'errorText': 'The md5sum of the summary statistics file does not match the one provided'},
                        {'id': 3, 'errorText': 'Summary statistics file validation failed, please run the validator on your file to see the errors (available here: https://pypi.org/project/ss-validate/)'},
                        {'id': 4, 'errorText': 'Missing mandatory field, you must provide (i) file path/URL, (ii) md5 sum and (iii) genome assembly for each file'},
                        {'id': 5, 'errorText': 'Genome assembly invalid - please see documentation for valid assemblies'},
                        {'id': 6, 'errorText': 'Summary statistics file validation failed: File extension error, please run the validator on your file to see the errors (available here: https://pypi.org/project/ss-validate/)'},
                        {'id': 7, 'errorText': 'Summary statistics file validation failed: File header error, please run the validator on your file to see the errors (available here: https://pypi.org/project/ss-validate/)'},
                        {'id': 8, 'errorText': 'Summary statistics file validation failed: File squareness error, please run the validator on your file to see the errors (available here: https://pypi.org/project/ss-validate/)'},
                        {'id': 9, 'errorText': 'Summary statistics file validation failed: File contains fewer than 100,000 rows. If you have fewer than 100,000 variants in your dataset, please contact gwas-subs@ebi.ac.uk for further advice.'},
                        {'id': 10, 'errorText': 'There is a problem on our side, please contact gwas-subs@ebi.ac.uk for further advice.'},
                        {'id': 11, 'errorText': 'The raw sumstats file can not be found'}
                    ]

VALID_ASSEMBLIES = ["GRCh38", "GRCh37", "NCBI36", "NCBI35", "NCBI34", "NR"]

NEXTFLOW_CONFIG = ("executor.name = 'lsf'\n"
                   "executor.queueSize = 100\n"
                   "singularity.cacheDir = '{sing_cache_dir}'\n").format(
        sing_cache_dir=_env_variable_else('SINGULARITY_CACHEDIR', './singularity_cache'))

SUBMISSION_TEMPLATE_HEADER_MAP_pre1_8 = {
    'Genotyping technology': 'genotypingTechnology',
    'Number of individuals': 'sampleSize',
    'Ancestry category': 'sampleAncestry',
    'Reported trait': 'traitDescription',
    'EAF lower limit': 'effectAlleleFreqLowerLimit',
    'Ancestry method': 'ancestryMethod',
    'Case control study': 'caseControlStudy',
    'Number of cases': 'caseCount',
    'Number of controls': 'controlCount',
    'Summary statistics assembly': 'genomeAssembly',
    'Neg Log10 p-values': 'pvalueIsNegLog10',
    'Analysis Software': 'analysisSoftware',
    'Imputation panel': 'imputationPanel',
    'Imputation software': 'imputationSoftware',
    'Adjusted covariates': 'adjustedCovariates',
    'Mapped trait': 'ontologyMapping',
    'Readme file': 'authorNotes'
}

SUBMISSION_TEMPLATE_HEADER_MAP = {
    'Genotyping technology': 'genotypingTechnology',
    'Number of individuals': 'sampleSize',
    'Ancestry category': 'sampleAncestry',
    'Reported trait': 'traitDescription',
    'EAF lower limit': 'effectAlleleFreqLowerLimit',
    'Ancestry method': 'ancestryMethod',
    'Case control study': 'caseControlStudy',
    'Number of cases': 'caseCount',
    'Number of controls': 'controlCount',
    'Summary statistics assembly': 'genomeAssembly',
    'Neg Log10 p-values': 'pvalueIsNegLog10',
    'Analysis Software': 'analysisSoftware',
    'Imputation panel': 'imputationPanel',
    'Imputation software': 'imputationSoftware',
    'Adjusted covariates': 'adjustedCovariates',
    'Mapped trait': 'ontologyMapping',
    'Readme text': 'authorNotes',
    'Coordinate system': 'coordinateSystem',
    'Sex': 'sex'
}

SUMSTATS_FILE_TYPE = _env_variable_else('SSF_VERSION', "GWAS-SFF v1.0")
GWAS_CATALOG_REST_API_STUDY_URL = "https://www.ebi.ac.uk/gwas/rest/api/studies/"
GWAS_DEPO_REST_API_URL = _env_variable_else('GWAS_DEPO_REST_API_URL',"https://www.ebi.ac.uk/gwas/deposition/api/v1/")
