from contextlib import contextmanager
from contextvars import ContextVar

_actor: ContextVar = ContextVar('audit_actor', default=None)


@contextmanager
def actor(user):
    token = _actor.set(user)
    try:
        yield
    finally:
        _actor.reset(token)


def get_actor():
    return _actor.get()
