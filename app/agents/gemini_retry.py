import time
from collections.abc import Callable
from typing import TypeVar

from google.genai import errors

T = TypeVar("T")


def with_retry(call: Callable[[], T], attempts: int = 3, delay: float = 3) -> T:
    for i in range(attempts):
        try:
            return call()
        except errors.APIError as error:
            if getattr(error, "code", None) in (429, 500, 503, 504) and i < attempts - 1:
                time.sleep(delay * (i + 1))
                continue
            raise
    raise ValueError("attempts must be at least 1")
