import os
from multiprocessing import Lock, Manager, Value
from multiprocessing.managers import SyncManager
from time import sleep
from typing import TypeVar

manager: SyncManager = Manager()
_used_set = manager.dict()
_used_lock = Lock()
T = TypeVar('T')


class Locker:
    def __init__(self, name):
        self.name = os.path.abspath(name)
        self.locked = False

    def __enter__(self):
        while True:
            with _used_lock:
                if self.name not in _used_set:
                    _used_set[self.name] = os.getpid()
                    self.locked = True
                    break
                elif _used_set[self.name] == os.getpid():
                    break
            sleep(1)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.locked:
            with _used_lock:
                del _used_set[self.name]


class Counter:
    __slots__ = ("_value", "lock")

    def __init__(self):
        self._value = Value("i", 0)
        self.lock = Lock()

    @property
    def value(self) -> int:
        with self.lock:
            return self._value.value

    def inc(self) -> int:
        with self.lock:
            self._value.value = self._value.value + 1
            return self._value.value

    def dec(self) -> int:
        with self.lock:
            self._value.value = self._value.value - 1
            return self._value.value

    def __bool__(self):
        return bool(self.value)


def init():
    pass
