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

import json
import os
import queue
import re
import secrets
import subprocess
from contextvars import ContextVar
from enum import Enum
from pathlib import Path

import requests
from loguru import logger

from . import constants, server
from .objs import InteractResult, CallResult, Result


class SandboxPath:
    def __init__(self, dirname: str, path: str):
        self._dirname = dirname
        self._path = path

    @property
    def full(self):
        """
        Returns the file's full path outside the sandbox.
        :return: full path
        """
        return constants.sandbox_path / self._dirname / self._path

    @property
    def sandbox(self):
        """
        Returns the file's full path within the sandbox.
        :return: sandbox path
        """
        return Path("/sandbox") / self._dirname / self._path

    @property
    def inner(self):
        """
        Returns the file's path within the Environment.
        :return: inner path
        """
        return Path(self._path)

    @property
    def stem(self):
        """
        The final path component, minus its last suffix.
        :return: stem
        """
        return Path(self._path).stem

    @property
    def parent(self):
        """
        The path's parent directory.
        :return: parent
        """
        return SandboxPath(self._dirname, os.path.dirname(self._path))

    def exists(self) -> bool:
        """
        Check if the file exists.
        :return: True if exists, False otherwise
        """
        return self.full.exists()

    def __str__(self):
        return str(self.sandbox)

    def __repr__(self):
        return repr(self.sandbox)


class SeccompRule(Enum):
    c_cpp = "c_cpp"
    c_cpp_file_io = "c_cpp_file_io"
    general = "general"
    golang = "golang"
    node = "node"
    none = "none"


def chmod(filepath: SandboxPath, mode: int):
    lazy_call(["chmod", oct(mode)[2:], filepath])


class SandboxUser(Enum):
    root = 0
    judge = 1500
    compile = 1600
    running = 1700
    nobody = 65534

    def readable(self, filepath: SandboxPath):
        lazy_call(["chgrp", self.name, filepath])
        chmod(filepath, 0o740)

    def writeable(self, filepath: SandboxPath):
        if not filepath.full.parent.exists():
            filepath.full.parent.mkdir(parents=True, exist_ok=True)
            chmod(filepath.parent, 0o777)
        if not filepath.exists():
            filepath.full.touch()
        lazy_call(["chgrp", self.name, filepath])
        chmod(filepath, 0o760)

    def executable(self, filepath: SandboxPath):
        lazy_call(["chgrp", self.name, filepath])
        chmod(filepath, 0o750)


local_session = None


def get_session():
    global local_session
    if local_session is None:
        local_session = requests.Session()
    return local_session


def send_request(op: str, dat: dict):
    headers = {
        "token": server.app.config["JUDGE_TOKEN"]
    }
    res = get_session().post(constants.judger_url + "/" + op, json=dat, headers=headers)
    return res.json()


lazy_queue: ContextVar[queue.Queue] = ContextVar("lazy_queue", default=None)


def lazy_call(cmd: list[str]):
    if lazy_queue.get() is None:
        lazy_queue.set(queue.Queue())
    lazy_queue.get().put(json.dumps(list(map(str, cmd))))


def collect_lazy_queue() -> list[list[str]]:
    ret = []
    q = lazy_queue.get()
    if q:
        while not q.empty():
            ret.append(json.loads(q.get()))
    return ret


def is_tle(res: CallResult):
    return res.return_code == 777777 and res.stdout == res.stderr == "TLE"


def call(cmd: list[str], user: SandboxUser = SandboxUser.root, stdin: str = "",
         timeout: float | None = None, cwd: str | None = None) -> CallResult:
    dat = {
        "cmd": list(map(str, cmd)),
        "user": user.name,
        "stdin": stdin,
        "timeout": timeout,
        "cwd": cwd,
        "cmds": collect_lazy_queue()
    }
    logger.debug(dat)
    data = send_request("call", dat)
    logger.debug(data)
    return CallResult(*data)


def run(cmd: list[str], tl: int = 1000, ml: int = 128, in_file: SandboxPath | None = None,
        out_file: SandboxPath | None = None,
        err_file: SandboxPath | None = None, seccomp_rule: SeccompRule | None = SeccompRule.general,
        user: SandboxUser = SandboxUser.nobody, cwd: str | None = None, save_seccomp_info: bool = False) -> Result:
    if seccomp_rule is SeccompRule.none:
        seccomp_rule = None
    dat = {
        "cmd": list(map(str, cmd)),
        "tl": tl,
        "ml": ml,
        "in_file": "/dev/null" if in_file is None else str(in_file),
        "out_file": "/dev/null" if out_file is None else str(out_file),
        "err_file": "/dev/null" if err_file is None else str(err_file),
        "seccomp_rule_name": None if seccomp_rule is None else seccomp_rule.name,
        "uid": user.value,
        "cwd": cwd,
        "cmds": collect_lazy_queue()
    }
    logger.debug(dat)
    data = send_request("judge", dat)
    logger.debug(data)
    ret = Result(**data)
    if ret.signal == 31 and save_seccomp_info:
        if os.path.exists("/var/log/dmesg"):
            txt = subprocess.check_output(["dmesg"]).decode("utf-8")
            lines = [line[line.find("] ") + 2:] for line in txt.split("\n") if "] " in line]
            target_line = -1
            for i in range(len(lines) - 1, -1, -1):
                if "signal: 31" in lines[i]:
                    target_line = i
                    break
            if target_line != -1:
                good_lines = lines[max(0, target_line - 10):target_line]
                pat = "(R[A-Z0-9]{2}):\\s([0-9a-f]+)\\s"
                need = ("RAX", "RDI", "RSI", "RDX", "R10", "R08", "R09")
                mp = dict(re.findall(pat, "\n".join(good_lines)))
                ret.seccomp_info = ", ".join(f"{k}=0x{mp.get(k, '0')}" for k in need)
    return ret


def interact_run(cmd: list[str], interact_cmd: list[str], tl: int = 1000, ml: int = 128,
                 in_file: SandboxPath | None = None,
                 out_file: SandboxPath | None = None,
                 err_file: SandboxPath | None = None, interact_err_file: SandboxPath | None = None,
                 seccomp_rule: SeccompRule | None = SeccompRule.general,
                 user: SandboxUser = SandboxUser.nobody, interact_user: SandboxUser = SandboxUser.nobody,
                 cwd: str | None = None):
    if seccomp_rule is SeccompRule.none:
        seccomp_rule = None
    dat = {
        "cmd": list(map(str, cmd)),
        "interact_cmd": list(map(str, interact_cmd)),
        "tl": tl,
        "ml": ml,
        "in_file": "/dev/null" if in_file is None else str(in_file),
        "out_file": "/dev/null" if out_file is None else str(out_file),
        "err_file": "/dev/null" if err_file is None else str(err_file),
        "interact_err_file": "/dev/null" if interact_err_file is None else str(interact_err_file),
        "seccomp_rule_name": None if seccomp_rule is None else seccomp_rule.name,
        "uid": user.value,
        "interact_uid": interact_user.value,
        "cwd": cwd,
        "cmds": collect_lazy_queue()
    }
    logger.debug(dat)
    data = send_request("interact_judge", dat)
    logger.debug(data)
    return InteractResult(**data)


def init():
    token_path = (constants.data_path / "TOKEN")
    new_token = secrets.token_urlsafe(33) if "JUDGE_SERVER_TOKEN" not in os.environ else os.environ[
        "JUDGE_SERVER_TOKEN"]
    try:
        res = requests.post(constants.judger_url + "/init", json={"token": new_token, "op": "init"}, timeout=10).text
        logger.debug("response of init: " + repr(res))
        if '"OK"' != res:
            if not token_path.is_file():
                logger.error("Failed to init judge token (old token not found)")
                exit()
            old_token = token_path.read_text()
            res1 = requests.post(constants.judger_url + "/init", json={"token": old_token, "op": "check"}).text
            logger.debug("response of init1: " + repr(res1))
            if '"OK"' != res1:
                logger.error("Failed to init judge token (old token not match)")
                exit()
            server.app.config["JUDGE_TOKEN"] = old_token
        else:
            token_path.write_text(new_token)
            server.app.config["JUDGE_TOKEN"] = new_token
        logger.info("Judge token set successful")
    except requests.ConnectTimeout:
        logger.error("Failed to init judge token (connect timeout)")
        exit()
    chmod(SandboxPath(".", "."), 0o777)
