from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import requests
from loguru import logger

from . import constants


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


@dataclass
class Result:
    cpu_time: int  # ms
    real_time: int  # ms
    memory: int  # Bytes
    signal: int
    exit_code: int
    error: str
    result: str
    error_id: int
    result_id: int
    judger_log: int = ""


@dataclass
class InteractResult:
    result: Result
    interact_result: Result


@dataclass
class CallResult:
    stdout: str
    stderr: str
    return_code: int


class SeccompRule(Enum):
    c_cpp = "c_cpp"
    c_cpp_file_io = "c_cpp_file_io"
    general = "general"
    golang = "golang"
    node = "node"


class SandboxUser(Enum):
    root = 0
    judge = 1500
    compile = 1600
    running = 1700
    nobody = 65534


def call(cmd: list[str], user: SandboxUser = SandboxUser.root, stdin: str = "",
         timeout: float | None = None) -> CallResult:
    dat = {
        "cmd": list(map(str, cmd)),
        "user": user.name,
        "stdin": stdin,
        "timeout": timeout
    }
    logger.debug(dat)
    res = requests.post(constants.judger_url + "/call", json=dat)
    data = res.json()
    logger.debug(data)
    return CallResult(*data)


def run(cmd: list[str], tl: int = 1000, ml: int = 128, in_file: SandboxPath | None = None,
        out_file: SandboxPath | None = None,
        err_file: SandboxPath | None = None, seccomp_rule: SeccompRule | None = SeccompRule.general,
        user: SandboxUser = SandboxUser.nobody) -> Result:
    dat = {
        "cmd": list(map(str, cmd)),
        "tl": tl,
        "ml": ml,
        "in_file": "/dev/null" if in_file is None else str(in_file),
        "out_file": "/dev/null" if out_file is None else str(out_file),
        "err_file": "/dev/null" if err_file is None else str(err_file),
        "seccomp_rule_name": None if seccomp_rule is None else seccomp_rule.name,
        "uid": user.value
    }
    logger.debug(dat)
    res = requests.post(constants.judger_url + "/judge", json=dat)
    data = res.json()
    logger.debug(data)
    return Result(**data)


def interact_run(cmd: list[str], interact_cmd: list[str], tl: int = 1000, ml: int = 128,
                 in_file: SandboxPath | None = None,
                 out_file: SandboxPath | None = None,
                 err_file: SandboxPath | None = None, interact_err_file: SandboxPath | None = None,
                 seccomp_rule: SeccompRule | None = SeccompRule.general,
                 user: SandboxUser = SandboxUser.nobody, interact_user: SandboxUser = SandboxUser.nobody):
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
        "interact_uid": interact_user.value
    }
    logger.debug(dat)
    res = requests.post(constants.judger_url + "/interact_judge", json=dat)
    data = res.json()
    logger.debug(data)
    return InteractResult(**data)
