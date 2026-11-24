"""One shared clock for the whole product, so a week of work can be replayed in minutes.

Normally `now()` is the real time. In simulation mode (NOWHERE_SIM=1, combined server only) the world's simulation endpoints move it forward: every part
that decides "what day is it", "how old is this mail", "when was this sent" asks this module instead of the operating system. Real-time things that are
not business time (login tokens, the webhook signature window, HTTP timeouts) keep using the real clock on purpose.
"""
import os
from datetime import datetime, timedelta

_offset = timedelta(0)


def enabled() -> bool:
    return os.getenv("NOWHERE_SIM") == "1"


def now() -> datetime:
    return datetime.now() + _offset


def set_now(target: datetime) -> None:
    global _offset
    _offset = target - datetime.now()


def reset() -> None:
    global _offset
    _offset = timedelta(0)
