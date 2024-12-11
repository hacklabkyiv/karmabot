import logging


def init_logger():
    logger_format = "%(asctime)s - %(filename)s %(funcName)s %(levelname)s - %(message)s"
    logging.basicConfig(format=logger_format)
    return logging.getLogger("karmabot")


logger = init_logger()
