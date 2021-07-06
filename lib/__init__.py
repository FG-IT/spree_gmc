import logging
import os
import sys
from logging.handlers import RotatingFileHandler

logger = logging.getLogger('shopify.' + __name__)
formatter = logging.Formatter('%(asctime)s [%(levelname)s]: %(message)s')
logger.setLevel(logging.DEBUG)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)


def set_logger_handler(log_file_name):
    # logger.removeHandler(stream_handler)

    work_dir = os.path.dirname(os.path.dirname(__file__))
    logs_dir = os.path.join(work_dir, 'logs')
    if not os.path.isdir(logs_dir):
        os.makedirs(logs_dir)
    log_path = os.path.join(logs_dir, log_file_name)
    level = logging.INFO
    max_bytes = 200 * 1024 ** 2
    fh = RotatingFileHandler(
        log_path, maxBytes=max_bytes, backupCount=5)
    fh.setLevel(level)
    formatter = logging.Formatter('%(asctime)s %(name)s [%(levelname)s]:%(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    return logger
