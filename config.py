DB_PATH = "./data/sumstats_meta.db"
STORAGE_PATH = "./data"
LOGGING_PATH = "./logs"
DB_SCHEMA = """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS studies (
            studyID TEXT NOT NULL UNIQUE,
            callbackID TEXT NOT NULL,
            filePath TEXT NOT NULL,
            md5 TEXT NOT NULL,
            assembly TEXT NOT NULL,
            retrieved INT CHECK (retrieved IN (0,1)),
            dataValid INT CHECK (dataValid IN (0,1)),
            errorCode INT,
            readme TEXT,
            FOREIGN KEY(errorCode) REFERENCES errors(id)
            );

            CREATE TABLE IF NOT EXISTS errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            errorText TEXT UNIQUE
            );

            BEGIN TRANSACTION;
            INSERT OR IGNORE INTO errors(errorText) VALUES("URL not found"); -- 1
            INSERT OR IGNORE INTO errors(errorText) VALUES("md5sum did not match the one provided"); -- 2
            INSERT OR IGNORE INTO errors(errorText) VALUES("Validation failed"); -- 3
            COMMIT;
            """
BROKER = "amqp"
BROKER_HOST = "rabbitmq"
BROKER_PORT = 5672
