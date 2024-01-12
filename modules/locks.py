from multiprocessing import Lock, Manager
from time import sleep

keys = ("create_submission", "create_problem")
manager = Manager()
locks = {k: Lock() for k in keys}

_used_set = set()
_used_lock = Lock()


class Locker:
    def __init__(self, name):
        self.name = name

    def __enter__(self):
        while True:
            with _used_lock:
                if self.name not in _used_set:
                    _used_set.add(self.name)
                    return
            sleep(1)

    def __exit__(self, exc_type, exc_val, exc_tb):
        with _used_lock:
            _used_set.remove(self.name)


class AtomicValue:
    def __init__(self, value):
        self._value = manager.Value('i', value)
        self.lock = Lock()

    @property
    def value(self):
        with self.lock:
            return self._value.value

    @value.setter
    def value(self, value):
        with self.lock:
            self._value.value = value
