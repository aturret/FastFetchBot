import logging
import os

from app.config import LOG_LEVEL, LOG_FILE_PATH

level_to_name = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class Logger:
    def __init__(
        self,
        name,
        log_level=level_to_name[LOG_LEVEL],
        log_file_dir=LOG_FILE_PATH,
        log_file_name=None,
    ):
        """
        A simple utility logger class.

        :param name: Name of the logger
        :param log_level: Logging level. Default is DEBUG
        :param log_file_dir: Path to log file directory
        :param log_file_name: Name of the log file
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(log_level)

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # If a log file path is provided, logs are written to the file.
        # and they are also printed to the console.
        if log_file_name and log_file_dir:
            if not os.path.exists(log_file_dir):
                os.makedirs(log_file_dir)
            log_file_path = os.path.join(log_file_dir, log_file_name)
            file_handler = logging.FileHandler(log_file_path)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

    def get_logger(self):
        return self.logger


logger = Logger(__name__).get_logger()
