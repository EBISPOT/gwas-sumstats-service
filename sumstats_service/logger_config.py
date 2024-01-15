from logging.handlers import RotatingFileHandler
import logging
import logging.config
import os
from sumstats_service import config

def setup_logging():
    # Construct the relative path to log.conf
    dir_path = os.path.dirname(os.path.realpath(__file__))  # Directory of the current file
    config_path = os.path.join(dir_path, '../log.conf')  # Path to log.conf

    # Load the logging configuration
    logging.config.fileConfig(config_path, disable_existing_loggers=False)

def setup_logging_celery():
    log_file = "./celery_task.log"

    # Create a file handler
    handler = RotatingFileHandler(log_file, maxBytes=10000000, backupCount=5)
    handler.setLevel(logging.INFO)

    # Create a logging format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)

    # Add the handler to the logger
    logger = logging.getLogger('celery')
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
