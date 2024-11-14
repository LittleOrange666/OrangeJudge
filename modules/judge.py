import os
import secrets
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import requests
from loguru import logger

from . import constants, server


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


def chmod(filepath: SandboxPath, mode: int):
    call(["chmod", oct(mode)[2:], filepath])


class SandboxUser(Enum):
    root = 0
    judge = 1500
    compile = 1600
    running = 1700
    nobody = 65534

    def readable(self, filepath: SandboxPath):
        call(["chgrp", self.name, filepath])
        chmod(filepath, 0o740)

    def writeable(self, filepath: SandboxPath):
        if not filepath.full.parent.exists():
            filepath.full.parent.mkdir(parents=True,exist_ok=True)
            chmod(filepath.parent, 0o777)
        if not filepath.exists():
            filepath.full.touch()
        call(["chgrp", self.name, filepath])
        chmod(filepath, 0o760)

    def executable(self, filepath: SandboxPath):
        call(["chgrp", self.name, filepath])
        chmod(filepath, 0o750)


def send_request(op: str, dat: dict):
    headers = {
        "token": server.app.config["JUDGE_TOKEN"]
    }
    res = requests.post(constants.judger_url + "/" + op, json=dat, headers=headers)
    return res.json()


def call(cmd: list[str], user: SandboxUser = SandboxUser.root, stdin: str = "",
         timeout: float | None = None) -> CallResult:
    dat = {
        "cmd": list(map(str, cmd)),
        "user": user.name,
        "stdin": stdin,
        "timeout": timeout
    }
    logger.debug(dat)
    data = send_request("call", dat)
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
    data = send_request("judge", dat)
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
    data = send_request("interact_judge", dat)
    logger.debug(data)
    return InteractResult(result=Result(**data["result"]), interact_result=Result(**data["interact_result"]))


def init():
    token_path = (constants.data_path / "TOKEN")
    new_token = secrets.token_urlsafe(33)
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
