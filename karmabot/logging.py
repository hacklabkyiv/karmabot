import logging


def init_logger():
    logger_format = "%(asctime)s - %(filename)s %(funcName)s %(levelname)s - %(message)s"
    logging.basicConfig(format=logger_format)
    logger_ = logging.getLogger("karmabot")
    logger_.addHandler(logging.StreamHandler())
    return logger_


logger = init_logger()
