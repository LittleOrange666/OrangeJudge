"""
OrangeJudge, a competitive programming platform

Copyright (C) 2024-2025 LittleOrange666 (orangeminecraft123@gmail.com)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import io
import json
import shutil
import subprocess
import uuid
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Callable, Any

from flask import abort, request
from loguru import logger

from . import locks, constants
from .constants import tmp_path


def system(s: str, cwd: Path = Path.cwd()) -> None:
    """
    Execute a system command in a specified directory.

    This function runs a system command using subprocess with shell=True.
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
    logger.info(f"system command in {str(cwd.absolute())!r}: {s}")
    subprocess.call(s, cwd=cwd.absolute(), shell=True)


def create_truncated(source: Path, target: Path) -> str:
    """
    Create a truncated version of the source file and save it to the target file.

    This function reads the content of the source file, truncates it if necessary,
    and writes the result to the target file. If the source file doesn't exist,
    an empty target file is created.

    Args:
        source (Path): The path to the source file to be read.
        target (Path): The path to the target file where the truncated content will be written.

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
    if not source.exists():
        target.touch()
        return ""
    file_stats = source.stat()
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
    target = Path(filename + "_partial")
    filename = Path(filename)
    if target.is_file():
        return read(target)
    file_stats = filename.stat()
    if file_stats.st_size <= 500:
        return read(filename)
    content = create_truncated(filename, target)
    return content


def read(filepath: Path, n: int = -1) -> str:
    with locks.Locker(filepath):
        with filepath.open() as f:
            return f.read(n)


def read_default(filepath: Path, *, default: str = "") -> str:
    if not filepath.is_file():
        return default
    with locks.Locker(filepath):
        return filepath.read_text()


def write(content: str, filename: Path) -> str:
    if not filename.parent.is_dir():
        filename.parent.mkdir(parents=True, exist_ok=True)
    with locks.Locker(filename):
        filename.write_text(content)
    return content


def write_binary(content: bytes, filename: Path) -> bytes:
    if not filename.parent.is_dir():
        filename.parent.mkdir(parents=True, exist_ok=True)
    with locks.Locker(filename):
        filename.write_bytes(content)
    return content


def append(content: str, filename: Path) -> str:
    with locks.Locker(filename):
        with filename.open("a") as f:
            f.write(content)
    return content


def read_json(filename: Path) -> dict:
    with locks.Locker(filename):
        with filename.open() as f:
            return json.load(f)


def write_json(obj, filename: Path) -> None:
    with locks.Locker(filename):
        with filename.open("w") as f:
            json.dump(obj, f, indent=2)


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
    def __init__(self, filename: Path):
        self.path = filename.absolute()
        self.lock = locks.Locker(self.path)
        self.dat = None

    def __enter__(self):
        self.lock.__enter__()
        with self.path.open() as f:
            self.dat = json.load(f)
        return self.dat

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.save()
        self.lock.__exit__(exc_type, exc_val, exc_tb)

    def save(self) -> None:
        with self.path.open("w") as f:
            json.dump(self.dat, f, indent=2)


class File:
    def __init__(self, filename: Path):
        self.path = filename.absolute()
        self.lock = locks.Locker(self.path)

    def __enter__(self):
        self.lock.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.lock.__exit__(exc_type, exc_val, exc_tb)

    def read(self) -> str:
        with self.path.open() as f:
            return f.read()

    def write(self, content: str) -> str:
        with self.path.open("w") as f:
            f.write(content)
            return content

    def append(self, content: str) -> str:
        with self.path.open("a") as f:
            f.write(content)
            return content


class TempFile(File):
    def __init__(self, end=""):
        super().__init__(tmp_path / (random_string() + end))

    def __exit__(self, exc_type, exc_val, exc_tb):
        super().__exit__(exc_type, exc_val, exc_tb)
        if self.path.is_file():
            self.path.unlink()


def random_string() -> str:
    return uuid.uuid4().hex


def init():
    pass


def to_int(text: str, return_code: int = 400) -> int:
    if not text.isdigit():
        abort(return_code)
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


def print_to_string(*args, **kwargs):
    output: io.StringIO
    with io.StringIO() as output:
        print(*args, file=output, **kwargs)
        return output.getvalue()


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
    if page <= 0:
        page = 1
    if page > page_cnt:
        page = page_cnt
    if rev:
        got_data = list(reversed(sql_obj.slice(max(0, cnt - page_size * page),
                                               cnt - page_size * (page - 1)).all()))
    else:
        got_data = sql_obj.slice(constants.page_size * (page - 1),
                                 min(cnt, constants.page_size * page)).all()
    displays = [1, page_cnt]
    displays.extend(range(max(2, page - 2), min(page_cnt, page + 2) + 1))
    return got_data, page_cnt, page, sorted(set(displays))


def move(src: Path, dst: Path):
    logger.debug(f"Moving {str(src)!r} to {str(dst)!r}")
    shutil.move(src, dst)


def copy(src: Path, dst: Path):
    logger.debug(f"Copying {str(src)!r} to {str(dst)!r}")
    shutil.copy(src, dst)


def delete(target: Path):
    logger.debug(f"Deleting {str(target)!r}")
    target.unlink()
