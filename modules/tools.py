import json
import os
from functools import partial
from typing import Callable

import infix
from datetime import datetime


def create_truncated(source: str, target: str) -> str:
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
    with open(os.path.join(*filename)) as f:
        return f.read(n)


def write(content: str, *filename: str) -> str:
    with open(os.path.join(*filename), "w") as f:
        f.write(content)
    return content


def read_json(*filename: str):
    with open(os.path.join(*filename)) as f:
        return json.load(f)


def write_json(obj, *filename: str):
    with open(os.path.join(*filename), "w") as f:
        json.dump(obj, f, indent=2)


def get_timestring() -> str:
    t = datetime.now()
    return f"{t.year}-{t.month}-{t.day} {t.hour}:{t.minute:0>2d}:{t.second:0>2d}"


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
