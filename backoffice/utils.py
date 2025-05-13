import logging

logger = logging.getLogger(__name__)


def ensure(condition_met, condition):
    if not condition_met:
        logger.error(f"Could not ensure {condition}")
        raise Exception(condition)


def absurd(condition):
    logger.error(f"Absurd that {condition}")
    raise Exception(condition)


def lower_email(email: str|None) -> str|None:
    if email:
        return email.lower()
    else:
        return None
