DB_PATH = "./data/sumstats_meta.db"
STORAGE_PATH = "./data"
LOGGING_PATH = "./logs"
DB_SCHEMA = """
            CREATE TABLE studies (
            studyID TEXT NOT NULL UNIQUE,
            callbackID TEXT NOT NULL,
            pmID TEXT NOT NULL,
            filePath TEXT NOT NULL UNIQUE,
            md5 TEXT NOT NULL,
            assembly TEXT NOT NULL,
            retrieved INT CHECK (retrieved IN (0,1)),
            dataValid INT CHECK (retrieved IN (0,1))
            );
            """
