import os


DB_PATH = "./data/sumstats_meta.db"
STORAGE_PATH = os.environ.get('STORAGE_PATH') if os.environ.get('STORAGE_PATH') else "./data"
LOGGING_PATH = "./logs"
BROKER = "amqp"
BROKER_HOST = "rabbitmq"
BROKER_PORT = 5672
VALIDATE_WITH_SSH = os.environ.get('VALIDATE_WITH_SSH') if os.environ.get('VALIDATE_WITH_SSH') else True
COMPUTE_FARM_LOGIN_NODE = os.environ.get('COMPUTE_FARM_LOGIN_NODE') if os.environ.get('COMPUTE_FARM_LOGIN_NODE') else None
COMPUTE_FARM_USERNAME = os.environ.get('COMPUTE_FARM_USERNAME') if os.environ.get('COMPUTE_FARM_USERNAME') else None
COMPUTE_FARM_QUEUE = 'production-rh74'
SINGULARITY_IMAGE = os.environ.get('SINGULARITY_IMAGE') if os.environ.get('SINGULARITY_IMAGE') else 'ebispot/gwas-sumstats-service'
SINGULARITY_TAG = os.environ.get('SINGULARITY_TAG') if os.environ.get('SINGULARITY_TAG') else 'latest'

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

