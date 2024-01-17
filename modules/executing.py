import json
import math
import os.path
import subprocess
import uuid

from modules import constants, tools
from modules.constants import exit_codes


def call(cmd: list[str], stdin: str = "", timeout: float | None = None) -> tuple[str, str, int]:
    print(" ".join(cmd))
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    ret = process.communicate(stdin.encode("utf8"), timeout=timeout)
    # print([ret[0].decode("utf8"), ret[1].decode("utf8")])
    return ret[0].decode("utf8"), ret[1].decode("utf8"), process.returncode


def TLE(result):
    return result == ("TLE", "TLE", 777777)


def create_name():
    return str(uuid.uuid4())


class Environment:
    __slots__ = ("lxc_name", "dirname", "prefix", "safe", "judge")

    def __init__(self, lxc_name: str = constants.lxc_name):
        self.lxc_name: str = lxc_name
        self.dirname: str = create_name()
        mkdir = ["sudo", "lxc-attach", "-n", self.lxc_name, "--", "mkdir", "/" + self.dirname]
        call(mkdir)
        self.prefix: list[str] = ["sudo", "lxc-attach", "-n", self.lxc_name, "--"]
        self.safe: list[str] = ["sudo", "-u", "nobody"]
        self.judge: list[str] = ["sudo", "-u", "judge"]
        # call(self.prefix + ["chmod", "750", "/" + self.dirname])

    def send_file(self, filepath: str) -> str:
        print("send", filepath)
        file_abspath = os.path.abspath(filepath)
        cmd = ["sudo", "cp", file_abspath, f"/var/lib/lxc/{self.lxc_name}/rootfs/{self.dirname}"]
        call(cmd)
        self.protected(filepath)
        return self.filepath(file_abspath)

    def get_file(self, filepath: str, source: None | str = None) -> None:
        file_abspath = os.path.abspath(filepath)
        if source is None:
            source = os.path.basename(filepath)
        cmd = ["sudo", "mv", f"/var/lib/lxc/{self.lxc_name}/rootfs/{self.dirname}/{source}",
               os.path.dirname(file_abspath)]
        call(cmd)

    def rm_file(self, filepath: str) -> None:
        cmd = ["sudo", "rm", f"/var/lib/lxc/{self.lxc_name}/rootfs" + self.filepath(filepath)]
        call(cmd)

    def filepath(self, filename: str) -> str:
        if filename.startswith("/" + self.dirname):
            return filename
        return "/" + self.dirname + "/" + (
            filename if filename.count("/") <= 2 and "__pycache__" in filename else os.path.basename(filename))

    def fullfilepath(self, filename: str) -> str:
        return f"/var/lib/lxc/{self.lxc_name}/rootfs" + self.filepath(filename)

    def simple_run(self, cmd: list[str]) -> tuple[str, str, int]:
        return call(self.prefix + cmd)

    def safe_run(self, cmd: list[str]) -> tuple[str, str, int]:
        return call(self.prefix + self.safe + cmd)

    def exist(self, filename: str):
        return os.path.exists(self.fullfilepath(filename))

    def writeable(self, *filenames: str):
        for filename in filenames:
            if not self.exist(filename):
                tools.create(self.fullfilepath(filename))
            filepath = self.filepath(filename)
            call(self.prefix + ["chgrp", "judge", filepath])
            call(self.prefix + ["chmod", "770", filepath])

    def executable(self, *filenames: str):
        for filename in filenames:
            filepath = self.filepath(filename)
            call(self.prefix + ["chmod", "755", filepath])

    def readable(self, *filenames: str):
        for filename in filenames:
            filepath = self.filepath(filename)
            call(self.prefix + ["chmod", "744", filepath])

    def safe_readable(self, *filenames: str):
        for filename in filenames:
            filepath = self.filepath(filename)
            call(self.prefix + ["chgrp", "judge", filepath])
            call(self.prefix + ["chmod", "740", filepath])

    def protected(self, *filenames: str):
        for filename in filenames:
            filepath = self.filepath(filename)
            call(self.prefix + ["chmod", "750", filepath])

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
                    repr(" ".join(cmd)), repr(" ".join(interact_cmd)), in_file, out_file, self.filepath(create_name())]
            return call(self.prefix + main, timeout=tl + 1)
        except subprocess.TimeoutExpired:
            return "TLE", "TLE", 777777

    def __del__(self):
        cmd = ["sudo", "lxc-attach", "-n", self.lxc_name, "--", "sudo", "rm", "-rf", "/" + self.dirname]
        call(cmd)


class Language:
    def __init__(self, name: str, branch: str | None = None):
        self.name = name
        self.data = tools.read_json(f"langs/{name}.json")
        self.branch = self.data["default_branch"] if branch is None else branch
        self.kwargs = self.data["branches"][self.branch]
        self.base_exec_cmd = self.get_execmd(
            "/judge/" + self.data["exec_name"].format("base_" + self.name, **self.kwargs))
        call(["sudo", "lxc-attach", "-n", constants.lxc_name, "--"] + ["chmod", "755", self.base_exec_cmd[-1]])

    def compile(self, filename: str, env: Environment) -> tuple[str, str]:
        if self.data["require_compile"]:
            new_filename = os.path.splitext(filename)[0]
            dirname = os.path.dirname(new_filename)
            new_filename = env.filepath(self.data["exec_name"].format(os.path.basename(new_filename), **self.kwargs))
            compile_cmd = self.data["compile_cmd"][:]
            for i in range(len(compile_cmd)):
                compile_cmd[i] = compile_cmd[i].format(filename, new_filename, **self.kwargs)
            out = env.simple_run(compile_cmd)
            env.executable(new_filename)
            new_filename = os.path.join(dirname, new_filename)
            if out[1] and out[2] != 0:
                print(out[1])
                return new_filename, out[1]
            return new_filename, ""
        return filename, ""

    def get_execmd(self, filename: str) -> list[str]:
        exec_cmd = self.data["exec_cmd"][:]
        for i in range(len(exec_cmd)):
            exec_cmd[i] = exec_cmd[i].format(filename, **self.kwargs)
        return exec_cmd

    def run(self, file: str, env: Environment, tasks: list[tuple[str, str]]) -> str:
        filename = env.send_file(file)
        filename, ce_msg = self.compile(filename, env)
        if ce_msg:
            tools.write(ce_msg, os.path.dirname(file), "ce_msg.txt")
            return "CE"
        exec_cmd = self.get_execmd(filename)
        for stdin, stdout in tasks:
            tools.create(stdout)
            out = env.runwithshell(exec_cmd, env.send_file(stdin), env.send_file(stdout), 10, 1000, self.base_exec_cmd)
            if TLE(out):
                return "TLE: Testing is limited by 10 seconds"
            result = {o[0]: o[1] for o in (s.split("=") for s in out[0].split("\n")) if len(o) == 2}
            print(result)
            print(out[1])
            if "1" == result.get("WIFSIGNALED", None):
                return "RE: " + "您的程式無法正常執行"
            exit_code = result.get("WEXITSTATUS", "0")
            if "153" == exit_code:
                return "OLE"
            if "0" != exit_code:
                if exit_code in exit_codes:
                    return "RE: " + exit_codes[exit_code]
                else:
                    return "RE: code=" + exit_code
            timeusage = 0
            if "time" in result and float(result["time"]) >= 0:
                timeusage = int(float(result["time"]) * 1000)
            memusage = 0
            if "mem" in result and float(result["mem"]) >= 0:
                memusage = (int(result["mem"]) - int(result["basemem"])) * int(result["pagesize"]) // 1000
            env.get_file(stdout)
            env.rm_file(stdin)
            return f"OK: {timeusage}ms, {memusage}KB"


langs: dict[str, Language] = {}

for lang in os.listdir("langs"):
    lang_name = os.path.splitext(lang)[0]
    keys = tools.read_json(f"langs/{lang_name}.json")["branches"].keys()
    for key in keys:
        langs[key] = Language(lang_name, key)
