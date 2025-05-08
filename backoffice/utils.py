import logging

logger = logging.getLogger(__name__)

def ensure(condition, message):
    if not condition:
        logger.error(f"Condition not met: {message}")
        raise Exception(message)