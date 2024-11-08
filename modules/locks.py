import os
from multiprocessing import Lock, Manager, Value
from multiprocessing.managers import SyncManager
from pathlib import Path
from time import sleep
from typing import TypeVar

manager: SyncManager = Manager()
_used_set = manager.dict()
_used_lock = Lock()
T = TypeVar('T')


class Locker:
    def __init__(self, name: Path):
        """
        Initializes a new Locker instance.

        Args:
            name (str): The name of the resource to be locked, typically a file path.
        """
        self.name = str(name.absolute())
        self.locked = False

    def __enter__(self):
        """
        Acquires the lock for the resource. This method is called when entering
        the runtime context related to this object.

        Returns:
            Locker: The Locker instance itself.
        """
        while True:
            with _used_lock:
                if self.name not in _used_set:
                    _used_set[self.name] = os.getpid()
                    self.locked = True
                    break
                elif _used_set[self.name] == os.getpid():
                    break
            sleep(1)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Releases the lock for the resource. This method is called when exiting
        the runtime context related to this object.

        Args:
            exc_type (type): The exception type, if an exception was raised.
            exc_val (Exception): The exception instance, if an exception was raised.
            exc_tb (traceback): The traceback object, if an exception was raised.
        """
        if self.locked:
            with _used_lock:
                del _used_set[self.name]


class Counter:
    __slots__ = ("_value", "lock")

    def __init__(self):
        """
        Initializes a new Counter instance with a starting value of 0.
        """
        self._value = Value("i", 0)
        self.lock = Lock()

    @property
    def value(self) -> int:
        """
        Retrieves the current value of the counter.

        Returns:
            int: The current value of the counter.
        """
        with self.lock:
            return self._value.value

    def inc(self) -> int:
        """
        Increments the counter by 1.

        Returns:
            int: The new value of the counter after incrementing.
        """
        with self.lock:
            self._value.value = self._value.value + 1
            return self._value.value

    def dec(self) -> int:
        """
        Decrements the counter by 1.

        Returns:
            int: The new value of the counter after decrementing.
        """
        with self.lock:
            self._value.value = self._value.value - 1
            return self._value.value

    def __bool__(self):
        """
        Evaluates the truthiness of the counter based on its value.

        Returns:
            bool: True if the counter's value is non-zero, False otherwise.
        """
        return bool(self.value)


def init():
    pass
