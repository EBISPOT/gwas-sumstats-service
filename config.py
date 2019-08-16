DB_PATH = "./data/sumstats_meta.db"
STORAGE_PATH = "./data"
LOGGING_PATH = "./logs"
DB_SCHEMA = """
            PRAGMA foreign_keys = ON;

            CREATE TABLE studies (
            studyID TEXT NOT NULL UNIQUE,
            callbackID TEXT NOT NULL,
            filePath TEXT NOT NULL,
            md5 TEXT NOT NULL,
            assembly TEXT NOT NULL,
            retrieved INT CHECK (retrieved IN (0,1)),
            dataValid INT CHECK (dataValid IN (0,1)),
            errorCode INT,
            FOREIGN KEY(errorCode) REFERENCES errors(id)
            );

            CREATE TABLE errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            errorText TEXT UNIQUE
            );

            BEGIN TRANSACTION;
            INSERT INTO errors(errorText) VALUES("URL not found"); -- 1
            INSERT INTO errors(errorText) VALUES("md5sum did not match the one provided"); -- 2
            INSERT INTO errors(errorText) VALUES("Validation failed"); -- 3
            COMMIT;
            """
BROKER = "amqp"
BROKER_HOST = "rabbitmq"
BROKER_PORT = 5672
