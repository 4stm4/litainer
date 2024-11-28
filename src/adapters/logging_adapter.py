import logging
from core.interfaces import LoggerPort

class LoggingAdapter(LoggerPort):

    def __init__(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('container_setup.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger()

    def info(self, message: str):
        self.logger.info(message)

    def error(self, message: str):
        self.logger.error(message)
