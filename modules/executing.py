import math
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Any

from . import constants, tools, datas, server
from .constants import lang_path


def call(cmd: list[Any], stdin: str = "", timeout: float | None = None) -> tuple[str, str, int]:
    """
    Execute a command in a subprocess and return its output, error, and return code.

    Args:
        cmd (list[Any]): The command to execute. Each element in the list should be a string or convertible to a string.
        stdin (str, optional): The input to provide to the command. Defaults to an empty string.
        timeout (float | None, optional): The maximum time to wait for the command to complete. If None, the default timeout is 30 seconds.

    Returns:
        tuple[str, str, int]: A tuple containing the command's standard output, standard error, and return code.
    """
    cmd = list(map(str, cmd))
    tools.log(*cmd)
    if timeout is None:
        timeout = 30
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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


class Environment:
    __slots__ = ("dirname", "prefix", "safe", "judge")

    def __init__(self):
        """
        Initialize the Environment class.

        This method sets up the environment by creating a directory with a random name,
        and initializing command prefixes for different execution contexts.
        """
        self.dirname: str = tools.random_string()
        (constants.lxc_root_path / self.dirname).mkdir(parents=True, exist_ok=True)
        self.prefix: list[str] = ["sudo", "lxc-attach", "-n", constants.lxc_name, "--"]
        self.safe: list[str] = ["sudo", "-u", "nobody"]
        self.judge: list[str] = ["sudo", "-u", "judge"]

    def path(self, path: str) -> SandboxPath:
        """
        Create a SandboxPath object for the given path.

        Args:
            path (str): The path to create a SandboxPath for.

        Returns:
            SandboxPath: A SandboxPath object representing the given path within the sandbox.
        """
        return SandboxPath(self.dirname, path)

    def send_file(self, filepath: Path, nxt: Callable[[SandboxPath], None] | None = None) -> SandboxPath:
        """
        Send a file to the sandbox environment.

        Args:
            filepath (Path): The path of the file to send.
            nxt (Callable[[SandboxPath], None] | None, optional): A function to call on the created SandboxPath. Defaults to None.

        Returns:
            SandboxPath: A SandboxPath object representing the file sent in the sandbox.
        """
        tools.log("send", filepath)
        out = self.path(filepath.name)
        tools.copy(filepath, out.full)
        if nxt is None:
            self.protected(out)
        else:
            nxt(out)
        return out

    def rename(self, filename: SandboxPath, newname: str) -> SandboxPath:
        """
        Rename a file in the sandbox environment.

        Args:
            filename (SandboxPath): The current SandboxPath of the file.
            newname (str): The new name for the file.

        Returns:
            SandboxPath: A new SandboxPath object representing the renamed file.
        """
        ret = self.path(newname)
        tools.move(filename.full, ret.full)
        return ret

    def get_file(self, filepath: Path, source: None | SandboxPath = None) -> None:
        """
        Retrieve a file from the sandbox environment.

        Args:
            filepath (Path): The destination path for the retrieved file.
            source (None | SandboxPath, optional): The source SandboxPath. If None, it's derived from filepath. Defaults to None.
        """
        if source is None:
            source = self.path(filepath.name)
        tools.move(source.full, filepath.absolute())

    def simple_path(self, filepath: SandboxPath) -> SandboxPath:
        """
        Simplify a SandboxPath by moving it to the root of the sandbox environment if necessary.

        Args:
            filepath (SandboxPath): The SandboxPath to simplify.

        Returns:
            SandboxPath: A simplified SandboxPath.
        """
        target = self.path(filepath.inner.name)
        if target.inner != filepath.inner:
            tools.move(filepath.full, target.full)
        return target

    def rm_file(self, filepath: Path) -> None:
        """
        Remove a file from the sandbox environment.

        Args:
            filepath (Path): The path of the file to remove.
        """
        tools.delete(self.path(filepath.name).full)

    def simple_run(self, cmd: list[str]) -> tuple[str, str, int]:
        """
        Run a command in the sandbox environment.

        Args:
            cmd (list[str]): The command to run.

        Returns:
            tuple[str, str, int]: A tuple containing (stdout, stderr, return_code).
        """
        return call(self.prefix + cmd)

    def safe_run(self, cmd: list[str]) -> tuple[str, str, int]:
        """
        Run a command in the sandbox environment as a non-privileged user.

        Args:
            cmd (list[str]): The command to run.

        Returns:
            tuple[str, str, int]: A tuple containing (stdout, stderr, return_code).
        """
        return call(self.prefix + self.safe + cmd)

    def judge_run(self, cmd: list[str]) -> tuple[str, str, int]:
        """
        Run a command in the sandbox environment as the judge user.

        Args:
            cmd (list[str]): The command to run.

        Returns:
            tuple[str, str, int]: A tuple containing (stdout, stderr, return_code).
        """
        return call(self.prefix + self.judge + cmd)

    def judge_writeable(self, *filenames: SandboxPath) -> None:
        """
        Make files writable by the judge user in the sandbox environment.

        Args:
            *filenames (SandboxPath): The SandboxPaths to make writable.
        """
        for filename in filenames:
            if not filename.exists():
                filename.full.touch()
            filepath = filename.sandbox
            call(self.prefix + ["chgrp", "judge", filepath])
            call(self.prefix + ["chmod", "760", filepath])

    def writeable(self, *filenames: SandboxPath) -> None:
        """
        Make files writable by all users in the sandbox environment.

        Args:
            *filenames (SandboxPath): The SandboxPaths to make writable.
        """
        for filename in filenames:
            if not filename.exists():
                filename.full.touch()
            filepath = filename.sandbox
            call(self.prefix + ["chmod", "766", filepath])

    def judge_executable(self, *filenames: SandboxPath) -> None:
        """
        Make files executable by the judge user in the sandbox environment.

        Args:
            *filenames (SandboxPath): The SandboxPaths to make executable.
        """
        for filename in filenames:
            filepath = filename.sandbox
            call(self.prefix + ["chgrp", "judge", filepath])
            call(self.prefix + ["chmod", "750", filepath])

    def executable(self, *filenames: SandboxPath) -> None:
        """
        Make files executable by all users in the sandbox environment.

        Args:
            *filenames (SandboxPath): The SandboxPaths to make executable.
        """
        for filename in filenames:
            filepath = filename.sandbox
            call(self.prefix + ["chmod", "755", filepath])

    def readable(self, *filenames: SandboxPath) -> None:
        """
        Make files readable by all users in the sandbox environment.

        Args:
            *filenames (SandboxPath): The SandboxPaths to make readable.
        """
        for filename in filenames:
            filepath = filename.sandbox
            call(self.prefix + ["chmod", "744", filepath])

    def judge_readable(self, *filenames: SandboxPath) -> None:
        """
        Make files readable by the judge user in the sandbox environment.

        Args:
            *filenames (SandboxPath): The SandboxPaths to make readable.
        """
        for filename in filenames:
            filepath = filename.sandbox
            call(self.prefix + ["chgrp", "judge", filepath])
            call(self.prefix + ["chmod", "740", filepath])

    def protected(self, *filenames: SandboxPath) -> None:
        """
        Make files accessible only by the owner in the sandbox environment.

        Args:
            *filenames (SandboxPath): The SandboxPaths to protect.
        """
        for filename in filenames:
            filepath = filename.sandbox
            call(self.prefix + ["chmod", "700", filepath])

    def runwithshell(self, cmd: list[str], in_file: SandboxPath, out_file: SandboxPath, tl: float, ml: int,
                     base_cmd: list[str]) -> tuple[str, str, int]:
        """
        Run a command with shell in the sandbox environment.

        Args:
            cmd (list[str]): The command to run.
            in_file (SandboxPath): The input file.
            out_file (SandboxPath): The output file.
            tl (float): Time limit in seconds.
            ml (int): Memory limit in MB.
            base_cmd (list[str]): The base command to run.

        Returns:
            tuple[str, str, int]: A tuple containing (stdout, stderr, return_code).
        """
        try:
            main = ["sudo", "/judge/shell", str(math.ceil(tl)), str(ml * 1024 * 1024),
                    str(100 * 1024 * 1024), repr(" ".join(base_cmd)),
                    repr(" ".join(cmd)), in_file.sandbox, out_file.sandbox]
            return call(self.prefix + main, timeout=tl + 1)
        except subprocess.TimeoutExpired:
            return "TLE", "TLE", 777777

    def runwithinteractshell(self, cmd: list[str], interact_cmd: list[str], in_file: SandboxPath, out_file: SandboxPath,
                             tl: float, ml: int, base_cmd: list[str]) -> tuple[str, str, int]:
        """
        Run a command with interactive shell in the sandbox environment.

        Args:
            cmd (list[str]): The command to run.
            interact_cmd (list[str]): The command to run interactor.
            in_file (SandboxPath): The input file.
            out_file (SandboxPath): The output file.
            tl (float): Time limit in seconds.
            ml (int): Memory limit in MB.
            base_cmd (list[str]): The base command to run.

        Returns:
            tuple[str, str, int]: A tuple containing (stdout, stderr, return_code).
        """
        try:
            main = ["sudo", "/judge/interact_shell", str(math.ceil(tl)), str(ml * 1024 * 1024),
                    str(100 * 1024 * 1024), repr(" ".join(base_cmd)),
                    repr(" ".join(cmd)), repr(" ".join(interact_cmd)), in_file.sandbox, out_file.sandbox,
                    self.path(tools.random_string())]
            return call(self.prefix + main, timeout=tl + 1)
        except subprocess.TimeoutExpired:
            return "TLE", "TLE", 777777

    def __del__(self):
        """
        Clean up the environment when the object is deleted.

        This method removes the directory created for this environment in the sandbox.
        """
        cmd = ["sudo", "lxc-attach", "-n", constants.lxc_name, "--", "sudo", "rm", "-rf", "/" + self.dirname]
        call(cmd)


class Language:
    """
    A class representing a programming language with its compilation and execution capabilities.

    Attributes:
    name (str): The name of the programming language.
    data (dict): The configuration data for the programming language.
    branch (str): The branch of the programming language.
    kwargs (dict): The keyword arguments for the programming language.
    base_exec_cmd (list[str]): The base execution command for the programming language.

    Methods:
    __init__(self, name: str, branch: str | None = None):
        Initializes the Language object with the given name and branch.

    compile(self, filename: SandboxPath, env: Environment, runner_filename: SandboxPath | None = None) -> tuple[SandboxPath, str]:
        Compiles the given source code file using the programming language.

    get_execmd(self, filename: SandboxPath) -> list[str]:
        Returns the execution command for the given source code file.

    supports_runner(self) -> bool:
        Checks if the programming language supports running a runner file.
    """

    def __init__(self, name: str, branch: str | None = None):
        self.name = name
        self.data = tools.read_json(lang_path / f"{name}.json")
        self.branch = self.data["default_branch"] if branch is None else branch
        self.kwargs = self.data["branches"][self.branch]
        base_name = "base_" + self.name
        if "base_name" in self.data:
            base_name = self.data["base_name"].format(**self.kwargs)
        exec_name = SandboxPath("judge", self.data["exec_name"].format(base_name, **self.kwargs))
        self.base_exec_cmd = self.get_execmd(exec_name)
        call(["sudo", "lxc-attach", "-n", constants.lxc_name, "--"] + ["chmod", "755", exec_name])

    def compile(self, filename: SandboxPath, env: Environment, runner_filename: SandboxPath | None = None) -> \
            tuple[SandboxPath, str]:
        if self.data["require_compile"]:
            if runner_filename is not None:
                if not self.supports_runner():
                    return filename, "Runner not supported"
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

    def supports_runner(self) -> bool:
        return "compile_runner_cmd" in self.data


def scheduled_restart_sandbox():
    while True:
        time.sleep(1800)
        with server.app.app_context():
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
