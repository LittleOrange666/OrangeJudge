import json
import os
import time
from datetime import datetime
from functools import partial
from typing import Callable

import infix
from flask import abort

from modules.locks import Locker


def create_truncated(source: str, target: str) -> str:
    if not exists(source):
        create(target)
        return ""
    file_stats = os.stat(source)
    if file_stats.st_size <= 500:
        content = read(source)
        write(content, target)
        return content
    content = read(source, n=500)
    content += "\n(truncated)"
    write(content, target)
    return content


def get_content(filename: str) -> str:
    partial = filename + "_partial"
    if os.path.isfile(partial):
        return read(partial)
    file_stats = os.stat(filename)
    if file_stats.st_size <= 500:
        return read(filename)
    content = create_truncated(filename, partial)
    return content


def create(*filename: str) -> None:
    with open(os.path.join(*filename), "w"):
        pass


def remove(*filename: str) -> None:
    try:
        os.remove(os.path.join(*filename))
    except FileNotFoundError:
        pass


def read(*filename: str, n: int = -1) -> str:
    with Locker(os.path.join(*filename)):
        with open(os.path.join(*filename)) as f:
            return f.read(n)


def read_default(*filename: str, default: str = "") -> str:
    if not exists(*filename):
        return default
    with Locker(os.path.join(*filename)):
        with open(os.path.join(*filename)) as f:
            return f.read()


def write(content: str, *filename: str) -> str:
    fn = os.path.join(*filename)
    if not os.path.isdir(os.path.dirname(fn)):
        os.makedirs(os.path.dirname(fn), exist_ok=True)
    with Locker(fn):
        with open(fn, "w") as f:
            f.write(content)
    return content


def write_binary(content: bytes, *filename: str) -> bytes:
    fn = os.path.join(*filename)
    if not os.path.isdir(os.path.dirname(fn)):
        os.makedirs(os.path.dirname(fn), exist_ok=True)
    with Locker(fn):
        with open(fn, "wb") as f:
            f.write(content)
    return content


def append(content: str, *filename: str) -> str:
    with Locker(os.path.join(*filename)):
        with open(os.path.join(*filename), "a") as f:
            f.write(content)
    return content


def read_json(*filename: str):
    with Locker(os.path.join(*filename)):
        with open(os.path.join(*filename)) as f:
            return json.load(f)


def write_json(obj, *filename: str):
    with Locker(os.path.join(*filename)):
        with open(os.path.join(*filename), "w") as f:
            json.dump(obj, f, indent=2)


def exists(*filename: str) -> bool:
    return os.path.exists(os.path.join(*filename))


def elapsed(*filename: str) -> float:
    ret = time.time() - os.path.getmtime(os.path.join(*filename))
    if ret < 0:
        return 100
    return ret


def get_timestring() -> str:
    t = datetime.now()
    return f"{t.year}-{t.month}-{t.day} {t.hour}:{t.minute:0>2d}:{t.second:0>2d}"


def form_json(s):
    try:
        return json.loads(s)
    except json.decoder.JSONDecodeError:
        abort(400)


J = infix.all_infix(os.path.join)


class Switcher:
    def __init__(self):
        self.table: dict[str, Callable] = {}
        self._default: Callable = lambda: None

    def bind_key(self, key: str, func: Callable):
        self.table[key] = func
        return func

    def bind(self, func: Callable | str):
        if type(func) is str:
            return partial(self.bind_key, func)
        self.table[func.__name__] = func
        return func

    def default(self, func: Callable):
        self._default = func
        return func

    def call(self, key, *args, **kwargs):
        return self.table.get(key, self._default)(*args, **kwargs)


class Json:
    def __init__(self, *filename: str):
        self.name = os.path.abspath(os.path.join(*filename))
        self.lock = Locker(self.name)
        self.dat = None

    def __enter__(self):
        self.lock.__enter__()
        with open(self.name) as f:
            self.dat = json.load(f)
        return self.dat

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.save()
        self.lock.__exit__(exc_type, exc_val, exc_tb)

    def save(self):
        with open(self.name, "w") as f:
            json.dump(self.dat, f, indent=2)


class File:
    def __init__(self, *filename: str):
        self.name = os.path.abspath(os.path.join(*filename))
        self.lock = Locker(self.name)

    def __enter__(self):
        self.lock.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.lock.__exit__(exc_type, exc_val, exc_tb)

    def read(self):
        with open(self.name) as f:
            return f.read()

    def write(self, content: str):
        with open(self.name, "w") as f:
            return f.write(content)

    def append(self, content: str):
        with open(self.name, "a") as f:
            return f.write(content)
