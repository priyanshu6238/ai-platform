import uuid
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def generate_random_int():
    return int(uuid.uuid4().int % 1e6)  # Callable for default_factory
