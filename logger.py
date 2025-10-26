import logging

logging.basicConfig(level=logging.INFO,
format="%(levelname)s - %(filename)s - %(asctime)s - %(name)s- %(message)s",
handlers=[logging.FileHandler("app.log"), logging.StreamHandler()])

logger = logging.getLogger(__name__)

def get_logger(filename: str) -> logging.Logger:
    return logging.getLogger(filename)