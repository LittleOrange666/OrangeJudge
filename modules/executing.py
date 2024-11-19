import shutil
from pathlib import Path
from typing import Callable

from loguru import logger

from . import constants, tools, judge
from .constants import lang_path
from .judge import SandboxPath, SandboxUser


class Environment:
    __slots__ = ("dirname", "cwd")

    def __init__(self):
        """
        Initialize the Environment class.

        This method sets up the environment by creating a directory with a random name,
        and initializing command prefixes for different execution contexts.
        """
        self.dirname: str = tools.random_string()
        self.cwd: SandboxPath = self.path("")
        self.cwd.full.mkdir(parents=True, exist_ok=True)
        judge.chmod(self.cwd, 0o777)

    def path(self, path: str) -> SandboxPath:
        """
        Create a SandboxPath object for the given path.

        Args:
            path (str): The path to create a SandboxPath for.

        Returns:
            SandboxPath: A SandboxPath object representing the given path within the sandbox.
        """
        return SandboxPath(self.dirname, path)

    def rand_path(self, suffix: str = "") -> SandboxPath:
        """
        Create a SandboxPath object for a random path within the sandbox.

        Args:
            suffix (str): The suffix to append to the random path.

        Returns:
            SandboxPath: A SandboxPath object representing the random path within the sandbox.
        """
        return self.path(tools.random_string()+suffix)

    def send_file(self, filepath: Path, nxt: Callable[[SandboxPath], None] | None = None) -> SandboxPath:
        """
        Send a file to the sandbox environment.

        Args:
            filepath (Path): The path of the file to send.
            nxt (Callable[[SandboxPath], None] | None, optional): A function to call on the created SandboxPath. Defaults to None.

        Returns:
            SandboxPath: A SandboxPath object representing the file sent in the sandbox.
        """
        logger.debug(f"send {filepath}")
        out = self.path(filepath.name)
        if not filepath.is_file():
            filepath.touch()
        tools.copy(filepath, out.full)
        if nxt is None:
            self.protected(out)
        else:
            nxt(out)
        return out

    def send_rand_file(self, filepath: Path, nxt: Callable[[SandboxPath], None] | None = None) -> SandboxPath:
        """
            Send a file to a random location in the sandbox environment.

            This function copies a file to a random path within the sandbox, optionally applies
            a custom function to the new file, and returns the new SandboxPath.

            Args:
                filepath (Path): The path of the file to send to the sandbox.
                nxt (Callable[[SandboxPath], None] | None, optional): A function to call on the
                    created SandboxPath. If None, the file will be protected. Defaults to None.

            Returns:
                SandboxPath: A SandboxPath object representing the randomly named file in the sandbox.
        """
        out = self.rand_path(filepath.suffix)
        logger.debug(f"send {filepath} to {out.sandbox}")
        if not filepath.is_file():
            filepath.touch()
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
        judge.call(["chown", "root:root", str(source.sandbox)])
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
    def writeable(*filenames: SandboxPath, user: SandboxUser | None = None) -> None:
        """
        Make files writable by all users in the sandbox environment.

        Args:
            *filenames (SandboxPath): The SandboxPaths to make writable.
            user (SandboxUser | None, optional): The user to make the files writable. Defaults to None (all_user).
        """
        for filename in filenames:
            if not filename.full.parent.exists():
                filename.full.parent.mkdir(parents=True, exist_ok=True)
                judge.chmod(filename.parent, 0o777)
            if not filename.exists():
                filename.full.touch()
            if user is None:
                judge.chmod(filename, 0o766)
            else:
                user.writeable(filename)

    @staticmethod
    def executable(*filenames: SandboxPath, user: SandboxUser | None = None) -> None:
        """
        Make files executable by all users in the sandbox environment.

        Args:
            *filenames (SandboxPath): The SandboxPaths to make executable.
            user (SandboxUser | None, optional): The user to make the files executable. Defaults to None (all_user).
        """
        for filename in filenames:
            if user is None:
                judge.chmod(filename, 0o755)
            else:
                user.executable(filename)

    @staticmethod
    def readable(*filenames: SandboxPath, user: SandboxUser | None = None) -> None:
        """
        Make files readable by all users in the sandbox environment.

        Args:
            *filenames (SandboxPath): The SandboxPaths to make readable.
            user (SandboxUser | None, optional): The user to make the files readable. Defaults to None (all_user).
        """
        for filename in filenames:
            if user is None:
                judge.chmod(filename, 0o744)
            else:
                user.executable(filename)

    @staticmethod
    def protected(*filenames: SandboxPath) -> None:
        """
        Make files accessible only by the owner in the sandbox environment.

        Args:
            *filenames (SandboxPath): The SandboxPaths to protect.
        """
        for filename in filenames:
            judge.chmod(filename, 0o700)

    def call(self, cmd: list[str], user: SandboxUser = SandboxUser.root, stdin: str = "",
             timeout: float | None = None) -> judge.CallResult:
        return judge.call(cmd, user, stdin, timeout, str(self.cwd))

    def run(self, cmd: list[str], tl: int = 1000, ml: int = 128, in_file: SandboxPath | None = None,
            out_file: SandboxPath | None = None,
            err_file: SandboxPath | None = None, seccomp_rule: judge.SeccompRule | None = judge.SeccompRule.general,
            user: SandboxUser = SandboxUser.nobody) -> judge.Result:
        return judge.run(cmd, tl, ml, in_file, out_file, err_file, seccomp_rule, user, str(self.cwd))

    def interact_run(self, cmd: list[str], interact_cmd: list[str], tl: int = 1000, ml: int = 128,
                     in_file: SandboxPath | None = None,
                     out_file: SandboxPath | None = None,
                     err_file: SandboxPath | None = None, interact_err_file: SandboxPath | None = None,
                     seccomp_rule: judge.SeccompRule | None = judge.SeccompRule.general,
                     user: SandboxUser = SandboxUser.nobody, interact_user: SandboxUser = SandboxUser.nobody) \
            -> judge.InteractResult:
        return judge.interact_run(cmd, interact_cmd, tl, ml, in_file, out_file, err_file, interact_err_file,
                                  seccomp_rule, user, interact_user, str(self.cwd))

    def __del__(self):
        """
        Clean up the environment when the object is deleted.

        This method removes the directory created for this environment in the sandbox.
        """
        shutil.rmtree(self.cwd.full)


class Language:
    """
    A class representing a programming language with compile and execution capabilities.

    Attributes:
    name (str): The name of the programming language.
    branch (str): The branch of the programming language.
    kwargs (dict): Keyword arguments for the programming language.
    base_exec_cmd (list[str]): The base execution command for the programming language.

    Methods:
    __init__(self, name: str, branch: str | None = None):
        Initializes the Language object with the given name and branch.

    compile(self, filename: SandboxPath, env: Environment, runner_filename: SandboxPath | None = None) -> tuple[SandboxPath, str]:
        Compiles the given source file using the programming language's compiler.
        Returns the compiled file's path and any compilation errors.

    get_execmd(self, filename: SandboxPath) -> list[str]:
        Returns the execution command for the given source file.

    supports_runner(self) -> bool:
        Returns True if the programming language supports running a runner file, False otherwise.
    """

    def __init__(self, name: str, branch: str | None = None):
        self.name = name
        self.data = tools.read_json(lang_path / f"{name}.json")
        self.branch = self.data["default_branch"] if branch is None else branch
        self.kwargs = self.data["branches"][self.branch]
        base_name = "base_" + self.name
        if "base_name" in self.data:
            base_name = self.data["base_name"].format(**self.kwargs)
        self.base_exec_name = base_name + self.data["source_ext"]
        self.base_time = 0
        self.base_memory = 0
        self.seccomp_rule = judge.SeccompRule.general
        if "seccomp_rule" in self.data:
            self.seccomp_rule = judge.SeccompRule[self.data["seccomp_rule"]]

    def compile(self, filename: SandboxPath, env: Environment, runner_filename: SandboxPath | None = None) -> \
            tuple[SandboxPath, str]:
        if self.data["require_compile"]:
            if runner_filename is not None:
                if not self.supports_runner():
                    return filename, "Runner not supported"
            new_filename = env.path(self.data["exec_name"].format(filename.stem, **self.kwargs))
            other_file = None
            SandboxUser.compile.executable(filename)
            if runner_filename is not None:
                compile_cmd = self.data["compile_runner_cmd"][:]
                if not self.supports_runner():
                    return filename, "Runner not supported"
                new_runner_filename = env.path(self.data["exec_name"].format(runner_filename.stem, **self.kwargs))
                for i in range(len(compile_cmd)):
                    compile_cmd[i] = compile_cmd[i].format(filename, new_filename, runner_filename, new_runner_filename,
                                                           **self.kwargs)
                SandboxUser.compile.executable(runner_filename)
                other_file = new_filename
                new_filename = new_runner_filename
            else:
                compile_cmd = self.data["compile_cmd"][:]
                for i in range(len(compile_cmd)):
                    compile_cmd[i] = compile_cmd[i].format(filename, new_filename, **self.kwargs)
            SandboxUser.compile.writeable(new_filename)
            out = env.call(compile_cmd, user=SandboxUser.compile)
            if judge.is_tle(out):
                logger.warning("Compiling TLE")
                return new_filename, "Compiling TLE"
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
            exec_cmd[i] = exec_cmd[i].format(filename.sandbox, filename.stem, folder=filename.sandbox.parent,
                                             **self.kwargs)
        return exec_cmd

    def supports_runner(self) -> bool:
        return "compile_runner_cmd" in self.data

    def update_base_resource_usage(self, env: Environment):
        logger.info(f"Updating base resource usage for {self.branch}")
        filename = env.send_file(constants.judge_path / self.base_exec_name)
        exec_filename, ce_msg = self.compile(filename, env)
        if ce_msg:
            logger.warning(f"Base resource usage for {self.branch} failed: CE")
        exec_cmd = self.get_execmd(exec_filename)
        res = env.run(exec_cmd, seccomp_rule=self.seccomp_rule)
        if res.result != "AC":
            logger.warning(f"Base resource usage for {self.branch} failed: {res.result}")
        else:
            self.base_time = res.cpu_time * 9 // 10
            self.base_memory = res.memory
            logger.info(f"Base resource usage for {self.branch}: {self.base_time} ms, {self.base_memory} B")


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
    env = Environment()
    for lang in langs.values():
        lang.update_base_resource_usage(env)
