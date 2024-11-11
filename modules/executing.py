import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable, Any

from loguru import logger

from . import constants, tools, datas, server, judge
from .constants import lang_path
from .judge import SandboxPath


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
    logger.debug(" ".join(cmd))
    if timeout is None:
        timeout = 30
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    ret = process.communicate(stdin.encode("utf8"), timeout=timeout)
    return ret[0].decode("utf8"), ret[1].decode("utf8"), process.returncode


def is_tle(result: tuple[str, str, int]) -> bool:
    return result == ("TLE", "TLE", 777777)


class Environment:
    __slots__ = ("dirname",)

    def __init__(self):
        """
        Initialize the Environment class.

        This method sets up the environment by creating a directory with a random name,
        and initializing command prefixes for different execution contexts.
        """
        self.dirname: str = tools.random_string()
        (constants.sandbox_path / self.dirname).mkdir(parents=True, exist_ok=True)

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
        logger.debug("send", filepath)
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

    @staticmethod
    def safe_run(cmd: list[str]) -> tuple[str, str, int]:
        """
        Run a command in the sandbox environment as a non-privileged user.

        Args:
            cmd (list[str]): The command to run.

        Returns:
            tuple[str, str, int]: A tuple containing (stdout, stderr, return_code).
        """
        res = judge.call(cmd, user=judge.SandboxUser.nobody)
        return res.stdout, res.stderr, res.return_code

    @staticmethod
    def judge_writeable(*filenames: SandboxPath) -> None:
        """
        Make files writable by the judge user in the sandbox environment.

        Args:
            *filenames (SandboxPath): The SandboxPaths to make writable.
        """
        for filename in filenames:
            if not filename.exists():
                filename.full.touch()
            filepath = filename.sandbox
            judge.call(["chgrp", "judge", filepath])
            judge.call(["chmod", "760", filepath])

    @staticmethod
    def writeable(*filenames: SandboxPath) -> None:
        """
        Make files writable by all users in the sandbox environment.

        Args:
            *filenames (SandboxPath): The SandboxPaths to make writable.
        """
        for filename in filenames:
            if not filename.exists():
                filename.full.touch()
            filepath = filename.sandbox
            judge.call(["chmod", "766", filepath])

    @staticmethod
    def judge_executable(*filenames: SandboxPath) -> None:
        """
        Make files executable by the judge user in the sandbox environment.

        Args:
            *filenames (SandboxPath): The SandboxPaths to make executable.
        """
        for filename in filenames:
            filepath = filename.sandbox
            judge.call(["chgrp", "judge", filepath])
            judge.call(["chmod", "750", filepath])

    @staticmethod
    def executable(*filenames: SandboxPath) -> None:
        """
        Make files executable by all users in the sandbox environment.

        Args:
            *filenames (SandboxPath): The SandboxPaths to make executable.
        """
        for filename in filenames:
            filepath = filename.sandbox
            judge.call(["chmod", "755", filepath])

    @staticmethod
    def readable(*filenames: SandboxPath) -> None:
        """
        Make files readable by all users in the sandbox environment.

        Args:
            *filenames (SandboxPath): The SandboxPaths to make readable.
        """
        for filename in filenames:
            filepath = filename.sandbox
            judge.call(["chmod", "744", filepath])

    @staticmethod
    def judge_readable(*filenames: SandboxPath) -> None:
        """
        Make files readable by the judge user in the sandbox environment.

        Args:
            *filenames (SandboxPath): The SandboxPaths to make readable.
        """
        for filename in filenames:
            filepath = filename.sandbox
            judge.call(["chgrp", "judge", filepath])
            judge.call(["chmod", "740", filepath])

    @staticmethod
    def protected(*filenames: SandboxPath) -> None:
        """
        Make files accessible only by the owner in the sandbox environment.

        Args:
            *filenames (SandboxPath): The SandboxPaths to protect.
        """
        for filename in filenames:
            filepath = filename.sandbox
            judge.call(["chmod", "700", filepath])

    def __del__(self):
        """
        Clean up the environment when the object is deleted.

        This method removes the directory created for this environment in the sandbox.
        """
        shutil.rmtree(constants.sandbox_path / self.dirname)


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
            out = judge.call(compile_cmd)
            if other_file is not None:
                other_file = env.simple_path(other_file)
                env.executable(other_file)
            new_filename = env.simple_path(new_filename)
            env.executable(new_filename)
            if out.stderr and out.return_code != 0:
                logger.warning(out.stderr)
                return new_filename, out.stderr
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


langs: dict[str, Language] = {}


def init():
    for lang_file in lang_path.iterdir():
        if lang_file.suffix != ".json":
            continue
        lang_name = lang_file.stem
        dat = tools.read_json(lang_file)
        keys = dat["branches"].keys()
        for key in keys:
            langs[key] = Language(lang_name, key)
