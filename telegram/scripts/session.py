#!/usr/bin/env python3
"""
Shared Telegram session lock helpers.
"""

from contextlib import contextmanager
from pathlib import Path
import fcntl
import time


@contextmanager
def session_lock(lock_file):
    path = Path(lock_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a+", encoding="utf-8")
    waited = False

    try:
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                if waited:
                    print("Telegram session lock acquired.")
                break
            except BlockingIOError:
                if not waited:
                    print("Waiting for Telegram session lock...")
                    waited = True
                time.sleep(1)

        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
