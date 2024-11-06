import json
import os
import subprocess
import time
import uuid
from datetime import datetime
from functools import partial
from typing import Callable, Any

from flask import abort, request

from . import locks, config, constants


def system(s: str, cwd: str = "") -> None:
    """
    Execute a system command in a specified directory.

    This function runs a system command using subprocess.call with shell=True.
    Caution: Using shell=True can be a security hazard if not used carefully.

    Args:
        s (str): The system command to be executed.
        cwd (str, optional): The directory in which to execute the command. 
                             Defaults to an empty string, which means the current directory.

    Returns:
        None

    Note:
        The function logs the command and its execution directory before running it.
    """
    cwd = os.path.abspath(cwd)
    log(f"system command in {cwd!r}:", s)
    subprocess.call(s, cwd=cwd, shell=True)


def create_truncated(source: str, target: str) -> str:
    """
    Create a truncated version of the source file and save it to the target file.

    This function reads the content of the source file, truncates it if necessary,
    and writes the result to the target file. If the source file doesn't exist,
    an empty target file is created.

    Args:
        source (str): The path to the source file to be read.
        target (str): The path to the target file where the truncated content will be written.

    Returns:
        str: The content that was written to the target file. This will be:
             - An empty string if the source file doesn't exist.
             - The full content if the source file is 500 bytes or smaller.
             - The first 500 bytes of the source file, followed by "\n(truncated)",
               if the source file is larger than 500 bytes.

    Note:
        This function relies on external functions such as 'exists', 'create',
        'read', and 'write', which are assumed to be defined elsewhere in the code.
    """
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
    """
    Retrieve the content of a file, potentially in a truncated form.

    This function attempts to read the content of a file. If a partial version
    of the file exists (with "_partial" appended to the filename), it returns
    the content of that partial file. Otherwise, it checks the size of the
    original file. If the file is 500 bytes or smaller, it returns the full
    content. For larger files, it creates a truncated version and returns that.

    Args:
        filename (str): The path to the file whose content should be retrieved.

    Returns:
        str: The content of the file. This could be:
             - The content of the partial file if it exists.
             - The full content of the original file if it's 500 bytes or smaller.
             - A truncated version of the content for larger files.

    Note:
        This function relies on external functions 'read' and 'create_truncated',
        which are assumed to be defined elsewhere in the code.
    """
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
    """
    A class that implements a simple switching mechanism for callable objects.

    This class allows binding functions to keys and provides methods to retrieve
    and call these functions based on the keys.
    """

    def __init__(self):
        """
        Initialize the Switcher with an empty table and a default function.
        """
        self.table: dict[str, Callable] = {}
        self._default: Callable = lambda: None

    def bind_key(self, key: str, func: Callable) -> Callable:
        """
        Bind a function to a specific key in the switcher.

        Args:
            key (str): The key to associate with the function.
            func (Callable): The function to be bound to the key.

        Returns:
            Callable: The function that was bound to the key.
        """
        self.table[key] = func
        return func

    def bind(self, func: Callable | str) -> Callable:
        """
        Bind a function to the switcher, using either the function's name as the key
        or a provided string key.

        Args:
            func (Callable | str): Either the function to bind or a string key.

        Returns:
            Callable: A decorator function if a string key is provided,
                      otherwise the function that was bound.
        """
        if type(func) is str:
            return partial(self.bind_key, func)
        self.table[func.__name__] = func
        return func

    def default(self, func: Callable) -> Callable:
        """
        Set the default function to be used when a key is not found.

        Args:
            func (Callable): The function to set as default.

        Returns:
            Callable: The function that was set as default.
        """
        self._default = func
        return func

    def get(self, key: str) -> Callable:
        """
        Get the function associated with a given key.

        Args:
            key (str): The key to look up.

        Returns:
            Callable: The function associated with the key, or the default function
                      if the key is not found.
        """
        return self.table.get(key, self._default)

    def call(self, key: str, *args, **kwargs) -> Any:
        """
        Call the function associated with a given key.

        Args:
            key (str): The key of the function to call.
            *args: Positional arguments to pass to the function.
            **kwargs: Keyword arguments to pass to the function.

        Returns:
            Any: The result of calling the function associated with the key,
                 or the result of calling the default function if the key is not found.
        """
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


def to_float(text: str) -> float:
    if text.count(".") > 1 or not text.replace(".", "").isdigit():
        abort(400)
    return float(text)


def to_datetime(text: str, **replace_kwargs) -> datetime:
    try:
        return datetime.fromtimestamp(to_float(text)).replace(**replace_kwargs)
    except ValueError:
        abort(400)


has_log: bool = config.debug.log.value


def log(*args):
    if has_log:
        print(*args)


def pagination(sql_obj, rev: bool = True, page: int | str | None = None, page_size: int = constants.page_size) -> \
        tuple[list, int, int, list[int]]:
    """
    Paginate the results of a SQL query.

    This function takes a SQL object (sql_obj) and optional parameters for
    reverse sorting (rev), current page (page), and page size (page_size).
    It returns a tuple containing the paginated results, the total number of pages,
    the current page number, and a list of valid page numbers for navigation.

    Args:
        sql_obj (SQL object): The SQL object representing the query results.
        rev (bool, optional): A boolean flag indicating whether the results should be sorted in reverse order.
            Defaults to True.
        page (int | str | None, optional): The current page number. If not provided, it will be
            retrieved from the request parameters. Defaults to None.
        page_size (int, optional): The number of results per page. Defaults to constants.page_size.

    Returns:
        tuple: A tuple containing the paginated results, the total number of pages,
            the current page number, and a list of valid page numbers for navigation.
    """
    cnt = sql_obj.count()
    page_cnt = max(1, (cnt - 1) // page_size + 1)
    if page is None:
        if request.method == "GET":
            page = request.args.get("page", "1")
        else:
            page = request.form.get("page", "1")
    if type(page) is str:
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
