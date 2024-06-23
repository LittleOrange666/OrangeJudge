import json
import os
import subprocess
import time
import uuid
from datetime import datetime
from functools import partial
from typing import Callable, Any

from flask import abort, request

from modules import locks, config, constants


def system(s: str, cwd: str = "") -> None:  # 此處使用了shell=True，請謹慎使用
    cwd = os.path.abspath(cwd)
    log(f"system command in {cwd!r}:", s)
    subprocess.call(s, cwd=cwd, shell=True)


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
    target = filename + "_partial"
    if os.path.isfile(target):
        return read(target)
    file_stats = os.stat(filename)
    if file_stats.st_size <= 500:
        return read(filename)
    content = create_truncated(filename, target)
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
    with locks.Locker(os.path.join(*filename)):
        with open(os.path.join(*filename)) as f:
            return f.read(n)


def read_default(*filename: str, default: str = "") -> str:
    if not exists(*filename):
        return default
    with locks.Locker(os.path.join(*filename)):
        with open(os.path.join(*filename)) as f:
            return f.read()


def write(content: str, *filename: str) -> str:
    fn = os.path.join(*filename)
    if not os.path.isdir(os.path.dirname(fn)):
        os.makedirs(os.path.dirname(fn), exist_ok=True)
    with locks.Locker(fn):
        with open(fn, "w") as f:
            f.write(content)
    return content


def write_binary(content: bytes, *filename: str) -> bytes:
    fn = os.path.join(*filename)
    if not os.path.isdir(os.path.dirname(fn)):
        os.makedirs(os.path.dirname(fn), exist_ok=True)
    with locks.Locker(fn):
        with open(fn, "wb") as f:
            f.write(content)
    return content


def append(content: str, *filename: str) -> str:
    with locks.Locker(os.path.join(*filename)):
        with open(os.path.join(*filename), "a") as f:
            f.write(content)
    return content


def read_json(*filename: str) -> dict:
    with locks.Locker(os.path.join(*filename)):
        with open(os.path.join(*filename)) as f:
            return json.load(f)


def write_json(obj, *filename: str) -> None:
    with locks.Locker(os.path.join(*filename)):
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


def form_json(s: str) -> dict:
    try:
        return json.loads(s)
    except json.decoder.JSONDecodeError:
        abort(400)


class Switcher:
    def __init__(self):
        self.table: dict[str, Callable] = {}
        self._default: Callable = lambda: None

    def bind_key(self, key: str, func: Callable) -> Callable:
        self.table[key] = func
        return func

    def bind(self, func: Callable | str) -> Callable:
        if type(func) is str:
            return partial(self.bind_key, func)
        self.table[func.__name__] = func
        return func

    def default(self, func: Callable) -> Callable:
        self._default = func
        return func

    def get(self, key: str) -> Callable:
        return self.table.get(key, self._default)

    def call(self, key: str, *args, **kwargs) -> Any:
        return self.table.get(key, self._default)(*args, **kwargs)


class Json:
    def __init__(self, *filename: str):
        self.name = os.path.abspath(os.path.join(*filename))
        self.lock = locks.Locker(self.name)
        self.dat = None

    def __enter__(self):
        self.lock.__enter__()
        with open(self.name) as f:
            self.dat = json.load(f)
        return self.dat

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.save()
        self.lock.__exit__(exc_type, exc_val, exc_tb)

    def save(self) -> None:
        with open(self.name, "w") as f:
            json.dump(self.dat, f, indent=2)


class File:
    def __init__(self, *filename: str):
        self.name = os.path.abspath(os.path.join(*filename))
        self.lock = locks.Locker(self.name)

    def __enter__(self):
        self.lock.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.lock.__exit__(exc_type, exc_val, exc_tb)

    def read(self) -> str:
        with open(self.name) as f:
            return f.read()

    def write(self, content: str) -> str:
        with open(self.name, "w") as f:
            f.write(content)
            return content

    def append(self, content: str) -> str:
        with open(self.name, "a") as f:
            f.write(content)
            return content


class TempFile(File):
    def __init__(self, end=""):
        super().__init__("tmp", random_string() + end)

    def __exit__(self, exc_type, exc_val, exc_tb):
        super().__exit__(exc_type, exc_val, exc_tb)
        os.remove(self.name)


def random_string() -> str:
    return uuid.uuid4().hex


def init():
    pass


def to_int(text: str) -> int:
    if not text.isdigit():
        abort(400)
    return int(text)


has_log: bool = config.get("debug.log")


def log(*args):
    if has_log:
        print(*args)


def pagination(sql_obj, rev: bool = True, page: int | str | None = None, page_size: int = constants.page_size):
    cnt = sql_obj.count()
    page_cnt = max(1, (cnt - 1) // page_size + 1)
    if page is None:
        if request.method == "GET":
            page = request.args.get("page", "1")
        else:
            page = request.form.get("page", "1")
    if type(page) == str:
        page = to_int(page)
    if page <= 0 or page > page_cnt:
        abort(404)
    if rev:
        got_data = list(reversed(sql_obj.slice(max(0, cnt - page_size * page),
                                               cnt - page_size * (page - 1)).all()))
    else:
        got_data = sql_obj.slice(constants.page_size * (page - 1),
                                 min(cnt, constants.page_size * page)).all()
    displays = [1, page_cnt]
    displays.extend(range(max(2, page - 2), min(page_cnt, page + 2) + 1))
    return got_data, page_cnt, page, sorted(set(displays))
