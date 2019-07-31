DB_PATH = "./data/sumstats_meta.db"
STORAGE_PATH = "./data"
LOGGING_PATH = "./logs"
DB_SCHEMA = """
            CREATE TABLE studies (
            studyID TEXT NOT NULL UNIQUE,
            callbackID TEXT NOT NULL,
            filePath TEXT NOT NULL,
            md5 TEXT NOT NULL,
            assembly TEXT NOT NULL,
            retrieved INT CHECK (retrieved IN (0,1)),
            dataValid INT CHECK (dataValid IN (0,1))
            );
            """
BROKER = "rabbitmq"
BROKER_HOST = "localhost"
BROKER_PORT = 5682
FILE_QUEUE = "file_queue"
VALIDATION_QUEUE = "validation_queue"
