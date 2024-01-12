import json
import os
import uuid

import requests


def tolinuxpath(winpath: str):
    path = os.path.abspath(winpath).replace("\\", "/")
    return "/mnt/" + path[0].lower() + path[2:]


class Executer:
    __slots__ = ("lxc_name", "dirname", "cmds", "prefix")

    def __init__(self, lxc_name: str = "lxc-test"):
        self.lxc_name: str = lxc_name
        self.dirname: str = str(uuid.uuid4())
        mkdir = ["sudo", "lxc-attach", "-n", self.lxc_name, "--", "mkdir", "/" + self.dirname]
        self.cmds: list[dict] = [{"cmd": mkdir}]
        self.prefix: list[str] = ["sudo", "lxc-attach", "-n", self.lxc_name, "--", "sudo", "-u", "nobody"]

    def send_file(self, filepath: str) -> str:
        file_abspath = tolinuxpath(filepath)
        cmd = ["sudo", "cp", file_abspath, f"/var/lib/lxc/{self.lxc_name}/rootfs/{self.dirname}"]
        self.cmds.append({"cmd": cmd})
        return self.filepath(os.path.basename(file_abspath))

    def filepath(self, filename: str) -> str:
        return "/" + self.dirname + "/" + filename

    def fullfilepath(self, filename: str) -> str:
        return f"/var/lib/lxc/{self.lxc_name}/rootfs/{self.dirname}/{filename}"

    def saferun(self, cmd: list[str], *args, **kwargs) -> int:
        return self.run(self.prefix + cmd, *args, **kwargs)

    def unsaferun(self, cmd: list[str], *args, **kwargs) -> int:
        return self.run(self.prefix[:-3] + cmd, *args, **kwargs)

    def run(self, cmd: list[str], getstdout: bool = True, getstderr: bool = True,
            timelimit: int = 10, stdin: str = "", stdin_file: str | None = None,
            stdout_file: str | None = None) -> int:
        obj = {"cmd": cmd, "getstdout": getstdout, "getstderr": getstderr, "timelimit": timelimit,
               "stdin": stdin}
        if stdin_file is not None:
            obj["stdin_file"] = stdin_file
        if stdout_file is not None:
            obj["stdout_file"] = stdout_file
        self.cmds.append(obj)
        return len(self.cmds) - 1

    def setmemory(self, memory: str) -> None:
        cmd = ["sudo", "lxc-cgroup", "-n", self.lxc_name, "memory.limit_in_bytes", memory]
        self.cmds.append({"cmd": cmd})

    def exec(self) -> list[dict]:
        # print(self.cmds)
        cmd = ["sudo", "lxc-attach", "-n", self.lxc_name, "--", "sudo", "rm", "-rf", "/" + self.dirname]
        self.cmds.append({"cmd": cmd})
        data = {"data": json.dumps(self.cmds)}
        responce = requests.post("http://localhost:7934/run", data)
        result = responce.json()
        mkdir = ["sudo", "lxc-attach", "-n", self.lxc_name, "--", "mkdir", "/" + self.dirname]
        self.cmds: list[dict] = [{"cmd": mkdir}]
        return result


class Language:
    def __init__(self, name: str, branch: str | None = None):
        file = f"langs/{name}.json"
        with open(file, "r") as f:
            self.data = json.load(f)
        self.branch = self.data["default_branch"] if branch is None else branch
        self.kwargs = self.data["branches"][self.branch]

    def run(self, file: str, runner: Executer, **kwargs) -> tuple[int, int]:
        runner.send_file(os.path.abspath(file))
        filename = runner.filepath(os.path.basename(file))
        cpid = -1
        if self.data["require_compile"]:
            new_filename = os.path.splitext(filename)[0]
            new_filename = self.data["exec_name"].format(os.path.dirname(new_filename), os.path.basename(new_filename),
                                                         **self.kwargs)
            compile_cmd = self.data["compile_cmd"][:]
            for i in range(len(compile_cmd)):
                compile_cmd[i] = compile_cmd[i].format(filename, new_filename, **self.kwargs)
            cpid = runner.unsaferun(compile_cmd)
            filename = new_filename
        exec_cmd = self.data["exec_cmd"][:]
        for i in range(len(exec_cmd)):
            exec_cmd[i] = exec_cmd[i].format(filename, **self.kwargs)
        runid = runner.saferun(exec_cmd, **kwargs)
        return cpid, runid


langs = {}

for lang in os.listdir("langs"):
    name = os.path.splitext(lang)[0]
    with open(f"langs/{name}.json") as f:
        keys = json.load(f)["branches"].keys()
    for key in keys:
        langs[key] = Language(name, key)
