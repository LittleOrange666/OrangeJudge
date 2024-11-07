import math
import os.path
import subprocess
from pathlib import Path
from typing import Callable

from constants import lang_path
from . import constants, tools, datas


def call(cmd: list[str], stdin: str = "", timeout: float | None = None) -> tuple[str, str, int]:
    tools.log(*cmd)
    if timeout is None:
        timeout = 30
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    ret = process.communicate(stdin.encode("utf8"), timeout=timeout)
    return ret[0].decode("utf8"), ret[1].decode("utf8"), process.returncode


def is_tle(result: tuple[str, str, int]) -> bool:
    return result == ("TLE", "TLE", 777777)


class Environment:
    """
    A class representing an environment for executing code in a Linux container.

    Attributes
    ----------
    lxc_name : str
        The name of the Linux container.
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
    __slots__ = ("lxc_name", "dirname", "prefix", "safe", "judge")

    def __init__(self, lxc_name: str = constants.lxc_name):
        self.lxc_name: str = lxc_name
        self.dirname: str = tools.random_string()
        mkdir = ["sudo", "lxc-attach", "-n", self.lxc_name, "--", "mkdir", "/" + self.dirname]
        call(mkdir)
        self.prefix: list[str] = ["sudo", "lxc-attach", "-n", self.lxc_name, "--"]
        self.safe: list[str] = ["sudo", "-u", "nobody"]
        self.judge: list[str] = ["sudo", "-u", "judge"]

    def get_lxc_root(self) -> str:
        """
        Returns the root path of the Linux container.
        :return: root path of the Linux container
        """
        return f"/var/lib/lxc/{self.lxc_name}/rootfs"

    def send_file(self, filepath: str, nxt: Callable[[str], None] | None = None) -> str:
        """
        Sends a file to the Linux container.
        :param filepath: file that will be sent
        :param nxt: action that will be performed after sending the file
        :return: filepath within the Linux container.
        """
        tools.log("send", filepath)
        file_abspath = os.path.abspath(filepath)
        cmd = ["sudo", "cp", file_abspath, f"{self.get_lxc_root()}/{self.dirname}"]
        call(cmd)
        if nxt is None:
            self.protected(filepath)
        else:
            nxt(filepath)
        return self.filepath(file_abspath)

    def rename(self, filename: str, nwname: str) -> str:
        folder = f"{self.get_lxc_root()}/{self.dirname}"
        cmd = ["sudo", "mv", f"{self.get_lxc_root()}{filename}", f"{folder}/{nwname}"]
        call(cmd)
        return self.filepath(nwname)

    def get_file(self, filepath: str, source: None | str = None) -> None:
        file_abspath = os.path.abspath(filepath)
        if source is None:
            source = os.path.basename(filepath)
        if self.dirname not in source:
            source = os.path.join("/" + self.dirname, source)
        cmd = ["sudo", "mv", self.get_lxc_root() + source,
               os.path.dirname(file_abspath)]
        call(cmd)

    def simple_path(self, filepath: str) -> str:
        target = os.path.basename(filepath)
        cmd = ["sudo", "mv", os.path.join(f"/{self.dirname}", filepath), f"/{self.dirname}/{target}"]
        if os.path.join(f"/{self.dirname}", filepath) != f"/{self.dirname}/{target}":
            self.simple_run(cmd)
        return target

    def rm_file(self, filepath: str) -> None:
        call(self.prefix + ["rm", self.filepath(filepath)])

    def filepath(self, filename: str) -> str:
        if filename.startswith("/" + self.dirname):
            return filename
        return "/" + self.dirname + "/" + (
            filename if filename.count("/") <= 2 and "__pycache__" in filename else os.path.basename(filename))

    def fullfilepath(self, filename: str) -> str:
        return self.get_lxc_root() + self.filepath(filename)

    def simple_run(self, cmd: list[str]) -> tuple[str, str, int]:
        return call(self.prefix + cmd)

    def safe_run(self, cmd: list[str]) -> tuple[str, str, int]:
        return call(self.prefix + self.safe + cmd)

    def judge_run(self, cmd: list[str]) -> tuple[str, str, int]:
        return call(self.prefix + self.judge + cmd)

    def exist(self, filename: str) -> bool:
        return os.path.exists(self.fullfilepath(filename))

    def judge_writeable(self, *filenames: str) -> None:
        for filename in filenames:
            if not self.exist(filename):
                Path(self.fullfilepath(filename)).touch()
            filepath = self.filepath(filename)
            call(self.prefix + ["chgrp", "judge", filepath])
            call(self.prefix + ["chmod", "760", filepath])

    def writeable(self, *filenames: str) -> None:
        for filename in filenames:
            if not self.exist(filename):
                Path(self.fullfilepath(filename)).touch()
            filepath = self.filepath(filename)
            call(self.prefix + ["chmod", "766", filepath])

    def judge_executable(self, *filenames: str) -> None:
        for filename in filenames:
            filepath = self.filepath(filename)
            call(self.prefix + ["chgrp", "judge", filepath])
            call(self.prefix + ["chmod", "750", filepath])

    def executable(self, *filenames: str) -> None:
        for filename in filenames:
            filepath = self.filepath(filename)
            call(self.prefix + ["chmod", "755", filepath])

    def readable(self, *filenames: str) -> None:
        for filename in filenames:
            filepath = self.filepath(filename)
            call(self.prefix + ["chmod", "744", filepath])

    def judge_readable(self, *filenames: str) -> None:
        for filename in filenames:
            filepath = self.filepath(filename)
            call(self.prefix + ["chgrp", "judge", filepath])
            call(self.prefix + ["chmod", "740", filepath])

    def protected(self, *filenames: str) -> None:
        for filename in filenames:
            filepath = self.filepath(filename)
            call(self.prefix + ["chmod", "700", filepath])

    def runwithshell(self, cmd: list[str], in_file: str, out_file: str, tl: float, ml: int, base_cmd: list[str]) \
            -> tuple[str, str, int]:
        try:
            main = ["sudo", os.path.abspath("/judge/shell"), str(math.ceil(tl)), str(ml * 1024 * 1024),
                    str(100 * 1024 * 1024), repr(" ".join(base_cmd)),
                    repr(" ".join(cmd)), in_file, out_file]
            return call(self.prefix + main, timeout=tl + 1)
        except subprocess.TimeoutExpired:
            return "TLE", "TLE", 777777

    def runwithinteractshell(self, cmd: list[str], interact_cmd: list[str], in_file: str, out_file: str, tl: float,
                             ml: int, base_cmd: list[str]) \
            -> tuple[str, str, int]:
        try:
            main = ["sudo", os.path.abspath("/judge/interact_shell"), str(math.ceil(tl)), str(ml * 1024 * 1024),
                    str(100 * 1024 * 1024), repr(" ".join(base_cmd)),
                    repr(" ".join(cmd)), repr(" ".join(interact_cmd)), in_file, out_file,
                    self.filepath(tools.random_string())]
            return call(self.prefix + main, timeout=tl + 1)
        except subprocess.TimeoutExpired:
            return "TLE", "TLE", 777777

    def __del__(self):
        cmd = ["sudo", "lxc-attach", "-n", self.lxc_name, "--", "sudo", "rm", "-rf", "/" + self.dirname]
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
        exec_name = "/judge/" + self.data["exec_name"].format(base_name, **self.kwargs)
        self.base_exec_cmd = self.get_execmd(exec_name)
        call(["sudo", "lxc-attach", "-n", constants.lxc_name, "--"] + ["chmod", "755", exec_name])

    def compile(self, filename: str, env: Environment, runner_filename: str | None = None) -> tuple[str, str]:
        if self.data["require_compile"]:
            if runner_filename is not None:
                if not self.supports_runner():
                    return filename, "Runner not supported"
            dirname = os.path.dirname(filename)
            new_filename = os.path.splitext(filename)[0]
            new_filename = env.filepath(self.data["exec_name"].format(os.path.basename(new_filename), **self.kwargs))
            other_file = None
            if runner_filename is not None:
                compile_cmd = self.data["compile_runner_cmd"][:]
                if not self.supports_runner():
                    return filename, "Runner not supported"
                new_runner_filename = os.path.splitext(runner_filename)[0]
                new_runner_filename = env.filepath(self.data["exec_name"].format(os.path.basename(new_runner_filename),
                                                                                 **self.kwargs))
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
            new_filename = os.path.join(dirname, new_filename)
            if out[1] and out[2] != 0:
                tools.log(out[1])
                return new_filename, out[1]
            return new_filename, ""
        env.executable(filename)
        return filename, ""

    def get_execmd(self, filename: str) -> list[str]:
        exec_cmd = self.data["exec_cmd"][:]
        for i in range(len(exec_cmd)):
            exec_cmd[i] = exec_cmd[i].format(filename,
                                             os.path.basename(os.path.splitext(filename)[0]),
                                             folder=os.path.dirname(filename), **self.kwargs)
        return exec_cmd

    def supports_runner(self):
        return "compile_runner_cmd" in self.data


langs: dict[str, Language] = {}


def init():
    for name in os.listdir("judge"):
        call(["sudo", "lxc-attach", "-n", constants.lxc_name, "--"] + ["chmod", "700", f"/judge/{name}"])
    call(["sudo", "lxc-attach", "-n", constants.lxc_name, "--"] + ["chmod", "755", f"/judge/__pycache__"])
    for lang in os.listdir("langs"):
        lang_name = os.path.splitext(lang)[0]
        dat = tools.read_json(lang_path / f"{lang_name}.json")
        keys = dat["branches"].keys()
        for key in keys:
            langs[key] = Language(lang_name, key)
        for s in dat.get("executables", []):
            call(["sudo", "lxc-attach", "-n", constants.lxc_name, "--"] + ["chmod", "755", s])
