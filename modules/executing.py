import math
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Any

from . import constants, tools, datas
from .constants import lang_path


def call(cmd: list[Any], stdin: str = "", timeout: float | None = None) -> tuple[str, str, int]:
    cmd = list(map(str, cmd))
    tools.log(*cmd)
    if timeout is None:
        timeout = 30
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    ret = process.communicate(stdin.encode("utf8"), timeout=timeout)
    return ret[0].decode("utf8"), ret[1].decode("utf8"), process.returncode


def is_tle(result: tuple[str, str, int]) -> bool:
    return result == ("TLE", "TLE", 777777)


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
        return constants.lxc_root_path / self._dirname / self._path

    @property
    def sandbox(self):
        """
        Returns the file's full path within the sandbox.
        :return: sandbox path
        """
        return Path("/") / self._dirname / self._path

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

    def __str__(self):
        return str(self.sandbox)

    def __repr__(self):
        return repr(self.sandbox)


class Environment:
    """
    A class representing an environment for executing code in a Linux container.

    Attributes
    ----------
    dirname : str
        The name of the directory created within the Linux container.
    prefix : list[str]
        The prefix for executing commands within the Linux container.
    safe : list[str]
        The command prefix for running commands as the nobody user.
    judge : list[str]
        The command prefix for running commands as the judge user.

    Methods
    -------
    get_lxc_root()
        Returns the root path of the Linux container.
    send_file(filepath: str, nxt: Callable[[str], None] | None = None) -> str
        Sends a file to the Linux container and returns the filepath.
    rename(filename: str, nwname: str) -> str
        Renames a file in the Linux container and returns the new filepath.
    get_file(filepath: str, source: str | None = None)
        Retrieves a file from the Linux container.
    simple_path(filepath: str) -> str
        Simplifies the filepath within the Linux container.
    rm_file(filepath: str)
        Removes a file from the Linux container.
    filepath(filename: str) -> str
        Returns the filepath within the Linux container.
    fullfilepath(filename: str) -> str
        Returns the full filepath within the Linux container.
    simple_run(cmd: list[str]) -> tuple[str, str, int]
        Runs a command within the Linux container and returns the output.
    safe_run(cmd: list[str]) -> tuple[str, str, int]
        Runs a command as a safe user within the Linux container and returns the output.
    judge_run(cmd: list[str]) -> tuple[str, str, int]
        Runs a command as the judge user within the Linux container and returns the output.
    exist(filename: str) -> bool
        Checks if a file exists within the Linux container.
    judge_writeable(*filenames: str)
        Makes files within the Linux container writeable by the judge user.
    writeable(*filenames: str)
        Makes files within the Linux container writeable.
    judge_executable(*filenames: str)
        Makes files within the Linux container executable by the judge user.
    executable(*filenames: str)
        Makes files within the Linux container executable.
    readable(*filenames: str)
        Makes files within the Linux container readable.
    judge_readable(*filenames: str)
        Makes files within the Linux container readable by the judge user.
    protected(*filenames: str)
        Makes files within the Linux container protected.
    runwithshell(cmd: list[str], in_file: str, out_file: str, tl: float, ml: int, base_cmd: list[str]) -> tuple[str, str, int]
        Runs a command within the Linux container using a shell and returns the output.
    runwithinteractshell(cmd: list[str], interact_cmd: list[str], in_file: str, out_file: str, tl: float, ml: int, base_cmd: list[str]) -> tuple[str, str, int]
        Runs a command within the Linux container using an interactive shell and returns the output.
    """
    __slots__ = ("dirname", "prefix", "safe", "judge")

    def __init__(self):
        self.dirname: str = tools.random_string()
        mkdir = ["sudo", "lxc-attach", "-n", constants.lxc_name, "--", "mkdir", "/" + self.dirname]
        call(mkdir)
        self.prefix: list[str] = ["sudo", "lxc-attach", "-n", constants.lxc_name, "--"]
        self.safe: list[str] = ["sudo", "-u", "nobody"]
        self.judge: list[str] = ["sudo", "-u", "judge"]

    def path(self, path: str) -> SandboxPath:
        return SandboxPath(self.dirname, path)

    def send_file(self, filepath: Path, nxt: Callable[[SandboxPath], None] | None = None) -> SandboxPath:
        """
        Sends a file to the Linux container.
        :param filepath: file that will be sent
        :param nxt: action that will be performed after sending the file
        :return: filepath within the Linux container.
        """
        tools.log("send", filepath)
        tools.copy(filepath, constants.lxc_root_path / self.dirname)
        out = self.path(filepath.name)
        if nxt is None:
            self.protected(out)
        else:
            nxt(out)
        return out

    def rename(self, filename: SandboxPath, nwname: str) -> SandboxPath:
        ret = self.path(nwname)
        tools.move(filename.full, ret.full)
        return ret

    def get_file(self, filepath: Path, source: None | SandboxPath = None) -> None:
        if source is None:
            source = self.path(filepath.name)
        tools.move(source.full, filepath.absolute())

    def simple_path(self, filepath: SandboxPath) -> SandboxPath:
        target = self.path(filepath.inner.name)
        if target.inner != filepath.inner:
            tools.move(filepath.full, target.full)
        return target

    def rm_file(self, filepath: Path) -> None:
        tools.delete(self.path(filepath.name).full)

    def simple_run(self, cmd: list[str]) -> tuple[str, str, int]:
        return call(self.prefix + cmd)

    def safe_run(self, cmd: list[str]) -> tuple[str, str, int]:
        return call(self.prefix + self.safe + cmd)

    def judge_run(self, cmd: list[str]) -> tuple[str, str, int]:
        return call(self.prefix + self.judge + cmd)

    def exist(self, filename: SandboxPath) -> bool:
        return filename.full.exists()

    def judge_writeable(self, *filenames: SandboxPath) -> None:
        for filename in filenames:
            if not self.exist(filename):
                filename.full.touch()
            filepath = filename.sandbox
            call(self.prefix + ["chgrp", "judge", filepath])
            call(self.prefix + ["chmod", "760", filepath])

    def writeable(self, *filenames: SandboxPath) -> None:
        for filename in filenames:
            if not self.exist(filename):
                filename.full.touch()
            filepath = filename.sandbox
            call(self.prefix + ["chmod", "766", filepath])

    def judge_executable(self, *filenames: SandboxPath) -> None:
        for filename in filenames:
            filepath = filename.sandbox
            call(self.prefix + ["chgrp", "judge", filepath])
            call(self.prefix + ["chmod", "750", filepath])

    def executable(self, *filenames: SandboxPath) -> None:
        for filename in filenames:
            filepath = filename.sandbox
            call(self.prefix + ["chmod", "755", filepath])

    def readable(self, *filenames: SandboxPath) -> None:
        for filename in filenames:
            filepath = filename.sandbox
            call(self.prefix + ["chmod", "744", filepath])

    def judge_readable(self, *filenames: SandboxPath) -> None:
        for filename in filenames:
            filepath = filename.sandbox
            call(self.prefix + ["chgrp", "judge", filepath])
            call(self.prefix + ["chmod", "740", filepath])

    def protected(self, *filenames: SandboxPath) -> None:
        for filename in filenames:
            filepath = filename.sandbox
            call(self.prefix + ["chmod", "700", filepath])

    def runwithshell(self, cmd: list[str], in_file: SandboxPath, out_file: SandboxPath, tl: float, ml: int,
                     base_cmd: list[str]) \
            -> tuple[str, str, int]:
        try:
            main = ["sudo", "/judge/shell", str(math.ceil(tl)), str(ml * 1024 * 1024),
                    str(100 * 1024 * 1024), repr(" ".join(base_cmd)),
                    repr(" ".join(cmd)), in_file.sandbox, out_file.sandbox]
            return call(self.prefix + main, timeout=tl + 1)
        except subprocess.TimeoutExpired:
            return "TLE", "TLE", 777777

    def runwithinteractshell(self, cmd: list[str], interact_cmd: list[str], in_file: SandboxPath, out_file: SandboxPath,
                             tl: float,
                             ml: int, base_cmd: list[str]) \
            -> tuple[str, str, int]:
        try:
            main = ["sudo", "/judge/interact_shell", str(math.ceil(tl)), str(ml * 1024 * 1024),
                    str(100 * 1024 * 1024), repr(" ".join(base_cmd)),
                    repr(" ".join(cmd)), repr(" ".join(interact_cmd)), in_file.sandbox, out_file.sandbox,
                    self.path(tools.random_string())]
            return call(self.prefix + main, timeout=tl + 1)
        except subprocess.TimeoutExpired:
            return "TLE", "TLE", 777777

    def __del__(self):
        cmd = ["sudo", "lxc-attach", "-n", constants.lxc_name, "--", "sudo", "rm", "-rf", "/" + self.dirname]
        call(cmd)


class Language:
    def __init__(self, name: str, branch: str | None = None):
        self.name = name
        self.data = tools.read_json(lang_path / f"{name}.json")
        self.branch = self.data["default_branch"] if branch is None else branch
        self.kwargs = self.data["branches"][self.branch]
        base_name = "base_" + self.name
        if "base_name" in self.data:
            base_name = self.data["base_name"].format(**self.kwargs)
        exec_name = SandboxPath("judge",self.data["exec_name"].format(base_name, **self.kwargs))
        self.base_exec_cmd = self.get_execmd(exec_name)
        call(["sudo", "lxc-attach", "-n", constants.lxc_name, "--"] + ["chmod", "755", exec_name])

    def compile(self, filename: SandboxPath, env: Environment, runner_filename: SandboxPath | None = None) -> tuple[
        SandboxPath, str]:
        if self.data["require_compile"]:
            if runner_filename is not None:
                if not self.supports_runner():
                    return filename, "Runner not supported"
            dirname = filename.sandbox.parent
            new_filename = env.path(self.data["exec_name"].format(filename.stem, **self.kwargs))
            other_file = None
            if runner_filename is not None:
                compile_cmd = self.data["compile_runner_cmd"][:]
                if not self.supports_runner():
                    return filename, "Runner not supported"
                new_runner_filename = env.path(self.data["exec_name"].format(runner_filename.stem, **self.kwargs))
                for i in range(len(compile_cmd)):
                    compile_cmd[i] = compile_cmd[i].format(filename, new_filename, runner_filename, new_runner_filename,
                                                           **self.kwargs)
                other_file = new_filename
                new_filename = new_runner_filename
            else:
                compile_cmd = self.data["compile_cmd"][:]
                for i in range(len(compile_cmd)):
                    compile_cmd[i] = compile_cmd[i].format(filename, new_filename, **self.kwargs)
            out = env.simple_run(compile_cmd)
            if other_file is not None:
                other_file = env.simple_path(other_file)
                env.executable(other_file)
            new_filename = env.simple_path(new_filename)
            env.executable(new_filename)
            if out[1] and out[2] != 0:
                tools.log(out[1])
                return new_filename, out[1]
            return new_filename, ""
        env.executable(filename)
        return filename, ""

    def get_execmd(self, filename: SandboxPath) -> list[str]:
        exec_cmd = self.data["exec_cmd"][:]
        for i in range(len(exec_cmd)):
            exec_cmd[i] = exec_cmd[i].format(filename, filename.stem, folder=filename.sandbox.parent, **self.kwargs)
        return exec_cmd

    def supports_runner(self):
        return "compile_runner_cmd" in self.data


def scheduled_restart_sandbox():
    while True:
        time.sleep(1800)
        while datas.Submission.query.filter_by(completed=False).count() > 0:
            time.sleep(60)
        call(["sudo", "lxc-stop", "-n", constants.lxc_name])
        call(["sudo", "lxc-start", "-n", constants.lxc_name])


langs: dict[str, Language] = {}


def init():
    for name in os.listdir("judge"):
        call(["sudo", "lxc-attach", "-n", constants.lxc_name, "--"] + ["chmod", "700", f"/judge/{name}"])
    call(["sudo", "lxc-attach", "-n", constants.lxc_name, "--"] + ["chmod", "755", f"/judge/__pycache__"])
    for lang_file in lang_path.iterdir():
        if lang_file.suffix != ".json":
            continue
        lang_name = lang_file.stem
        dat = tools.read_json(lang_file)
        keys = dat["branches"].keys()
        for key in keys:
            langs[key] = Language(lang_name, key)
        for s in dat.get("executables", []):
            call(["sudo", "lxc-attach", "-n", constants.lxc_name, "--"] + ["chmod", "755", s])
    restarter = threading.Thread(target=scheduled_restart_sandbox)
    restarter.daemon = True
    restarter.start()
