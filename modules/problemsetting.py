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

import dataclasses
import datetime
import json
import os
import shutil
import time
import traceback
from graphlib import TopologicalSorter, CycleError
from multiprocessing import Queue, Process
from pathlib import Path
from typing import Callable
from xml.etree import ElementTree
from xml.etree.ElementTree import Element

from flask import Response, abort, request, redirect
from loguru import logger
from pyzipper import AESZipFile
from pyzipper.zipfile_aes import AESZipInfo
from sqlalchemy.orm.attributes import flag_modified
from werkzeug.datastructures import ImmutableMultiDict, MultiDict
from werkzeug.utils import secure_filename

from . import executing, tools, constants, createhtml, datas, objs, judge, createhtml2
from .constants import tmp_path, preparing_problem_path, testlib, problem_path
from .judge import SandboxPath, SandboxUser
from .objs import ProgramType, GenType
from .routers.general import render_problem
from .server import sending_file
from .tools import TempFile

worker_queue = Queue()

root_folder = Path.cwd()
background_actions = tools.Switcher()
actions = tools.Switcher()
current_pid = ""
current_idx = 0


def make_important(func: Callable) -> Callable:
    func.important = True
    return func


class StopActionException(Exception):
    pass


def just_compile(path: Path, name: str, lang: executing.Language, env: executing.Environment) -> SandboxPath:
    log(f"compile {name} ({path.name})")
    file = env.send_file(path)
    exec_file, ce_msg = lang.compile(file, env)
    if ce_msg:
        log(f"{name} CE")
        log(ce_msg)
        end(False)
    return exec_file


def do_compile(path: Path, name: str, lang: executing.Language, env: executing.Environment) -> list[str]:
    return lang.get_execmd(just_compile(path, name, lang, env))


class Problem(objs.ProblemInfo):
    def __init__(self, pid: str, is_important_editing_now: bool = True):
        """
        Initialize the Problem class.

        This method initializes the Problem instance with the given problem ID and editing status.
        It retrieves the problem data from the database and sets the editing status if necessary.

        Args:
            pid (str): The problem ID.
            is_important_editing_now (bool, optional): Flag indicating if the problem is currently being edited. Defaults to True.
        """
        self.pid = pid
        self.is_important_editing_now = is_important_editing_now
        self.sql_data: datas.Problem = datas.first(datas.Problem, pid=pid)
        if self.is_important_editing_now:
            self.sql_data.editing = True
            datas.add(self.sql_data)
        super().__init__(**self.sql_data.new_data)

    def __enter__(self):
        """
        Enter the runtime context related to this object.

        Returns:
            Problem: The current instance of the Problem class.
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit the runtime context related to this object.

        This method updates the problem data in the database and resets the editing status if necessary.

        Args:
            exc_type: The exception type.
            exc_val: The exception value.
            exc_tb: The traceback object.
        """
        self.sql_data.new_datas = self
        self.sql_data.name = self.name
        if self.is_important_editing_now:
            self.sql_data.editing = False
            self.sql_data.edit_time = datetime.datetime.now()
        datas.add(self.sql_data)

    def save(self):
        """
        Save the current problem data to the database.

        This method updates the problem data in the database and marks the data as modified.
        """
        self.sql_data.new_datas = self
        self.sql_data.data = self.sql_data.new_data
        flag_modified(self.sql_data, "data")
        flag_modified(self.sql_data, "new_data")
        datas.add(self.sql_data)

    def lang(self, name) -> executing.Language:
        """
        Get the language configuration for the given file name.

        Args:
            name (str): The name of the file.

        Returns:
            executing.Language: The language configuration for the file.
        """
        fs = [o.type for o in self.files if o.name == name]
        if len(fs):
            return executing.langs[fs[0]]
        else:
            log(f"file {name} not found")
            end(False)

    def lang_of(self, fileinfo: objs.ProgramPtr) -> executing.Language:
        """
        Get the language configuration for the given file information.

        Args:
            fileinfo (objs.ProgramPtr): The file information object.

        Returns:
            executing.Language: The language configuration for the file.
        """
        if fileinfo.type == objs.ProgramType.default:
            return executing.langs[constants.default_lang]
        fs = [o.type for o in self.files if o.name == fileinfo.name]
        if len(fs):
            return executing.langs[fs[0]]
        else:
            log(f"file {fileinfo.name} not found")
            end(False)

    def compile_inner(self, filename: str, name: str, env: executing.Environment) -> list[str]:
        """
        Compile the given file in the specified environment.

        Args:
            filename (str): The name of the file to compile.
            name (str): The name of the compilation task.
            env (executing.Environment): The environment to use for compilation.

        Returns:
            list[str]: The compilation command.
        """
        lang = self.lang(filename)
        path = self.path / "file" / filename
        return do_compile(path, name, lang, env)

    def get_path(self, fileinfo: objs.ProgramPtr, filetype: str) -> Path:
        """
        Get the file path for the given file information and type.

        Args:
            fileinfo (objs.ProgramPtr): The file information object.
            filetype (str): The type of the file.

        Returns:
            Path: The file path.
        """
        path = (Path(
            f"testlib/{filetype}s") if fileinfo.type is ProgramType.default else self.path / "file") / fileinfo.name
        return path

    def compile_dat(self, fileinfo: objs.ProgramPtr, name: str, env: executing.Environment) -> SandboxPath:
        """
        Compile the given data file in the specified environment.

        Args:
            fileinfo (objs.ProgramPtr): The file information object.
            name (str): The name of the compilation task.
            env (executing.Environment): The environment to use for compilation.

        Returns:
            SandboxPath: The path to the compiled file.
        """
        path = self.get_path(fileinfo, name)
        lang = executing.langs[constants.default_lang] if fileinfo.type is ProgramType.default else self.lang(
            fileinfo.name)
        return just_compile(path, name, lang, env)

    def check_missing(self, fileinfo: objs.ProgramPtr, name: str):
        """
        Check if the given file exists.

        Args:
            fileinfo (objs.ProgramPtr): The file information object.
            name (str): The name of the file.

        Returns:
            bool: True if the file exists, False otherwise.
        """
        path = self.get_path(fileinfo, name)
        if not path.is_file():
            log(f"{name} missing: {path} not found")
            end(False)

    @property
    def path(self) -> Path:
        """
        Get the path to the problem directory.

        Returns:
            Path: The path to the problem directory.
        """
        return preparing_problem_path / self.pid


problem: Problem | None = None


def init() -> None:
    global root_folder
    root_folder = Path.cwd().absolute()
    Process(target=runner).start()


def create_problem(name: str, pid: str, user: datas.User) -> str:
    problem_count = datas.count(datas.Problem)
    if len(name) == 0 or len(name) > 120:
        abort(400)
    if pid:
        if constants.problem_id_reg.match(pid) is None:
            abort(400)
        if datas.count(datas.Problem, pid=pid) > 0:
            abort(409)
    else:
        pidx = problem_count + 1000
        while datas.count(datas.Problem, pid=str(pidx)) > 0:
            pidx += 1
        pid = str(pidx)
    dat = datas.Problem(id=problem_count + 1, pid=pid, name=name, data={}, user=user)
    path = preparing_problem_path / pid
    path.mkdir(parents=True, exist_ok=True)
    (path / "testcases").mkdir(parents=True, exist_ok=True)
    (path / "file").mkdir(parents=True, exist_ok=True)
    (path / "public_file").mkdir(parents=True, exist_ok=True)
    info = objs.ProblemInfo(name=name, users=[user.username])
    dat.datas = dat.new_datas = info
    datas.add(dat)
    return pid


def log(s: str, success: bool | None = None):
    logger.info(s)
    if not s.endswith("\n"):
        s += "\n"
    tools.append(s, preparing_problem_path / current_pid / "actions" / f"{current_idx}.log")
    if type(success) is bool:
        end(success)


def end(success: bool):
    with tools.Json(preparing_problem_path / current_pid / "actions" / f"{current_idx}.json") as dat:
        dat["success"] = success
        dat["completed"] = True
    raise StopActionException()


@background_actions.bind
def generate_testcase(pid: str):
    log(f"generating testcase")
    env = executing.Environment()
    env.send_file(testlib, env.executable)
    gen_list: list[objs.Testcase] = []
    int_cmd = []
    run_cmds = {}

    def get_cmd(s: str, title: str):
        if s not in run_cmds:
            run_cmds[s] = problem.compile_inner(s, title, env)
        return run_cmds[s]

    if problem.is_interact:
        int_cmd = get_cmd(problem.interactor_source, "interactor")
    tl = int(problem.timelimit)
    ml = int(problem.memorylimit)
    log("clear folder")
    testcase_path = problem.path / "testcases_gen"
    if testcase_path.is_dir():
        shutil.rmtree(testcase_path)
    testcase_path.mkdir(parents=True, exist_ok=True)
    log("complete clear folder")
    for group_id, gen_group in enumerate(problem.gen_groups):
        file1_cmd = get_cmd(gen_group.file1, "generator")
        file2_cmd = get_cmd(gen_group.file2, "solution" if gen_group.type is GenType.sol else "ans_generator")
        cur: list[objs.Testcase] = []
        for tcidx, cmd in enumerate(gen_group.cmds):
            name = f"{group_id}_{tcidx}"
            in_file = testcase_path / f"{name}.in"
            out_file = testcase_path / f"{name}.out"
            log(f"generating testcase {name!r}")
            gen_out = env.call(file1_cmd + cmd.split(), user=SandboxUser.judge)
            if judge.is_tle(gen_out):
                log("generator TLE")
                gen_group.status = "生成失敗：生成器TLE"
                break
            if gen_out.return_code:
                log("generator RE")
                gen_group.status = "生成失敗：生成器RE"
                log(gen_out.stderr)
                break
            tools.write(gen_out.stdout, in_file)
            if gen_group.type is GenType.sol:
                in_path = env.send_file(in_file)
                out_path = env.path(out_file.name)
                if problem.is_interact:
                    env.readable(in_path, user=SandboxUser.judge)
                    env.writeable(out_path, user=SandboxUser.judge)
                    res = env.interact_run(file2_cmd, int_cmd, tl, ml, in_path, out_path,
                                           interact_user=SandboxUser.judge).result
                else:
                    res = env.run(file2_cmd, tl, ml, in_path, out_path)
                if res.result != "AC":
                    logger.info(f"solution {res.result}")
                    gen_group.status = f"生成失敗：官解{res.result}"
                env.get_file(out_file, out_path)
            else:
                gen_out = env.call(file2_cmd + cmd.split(), user=SandboxUser.judge)
                if judge.is_tle(gen_out):
                    log("ans generator TLE")
                    gen_group.status = "生成失敗：答案生成器TLE"
                    break
                if gen_out.return_code:
                    log("ans generator RE")
                    gen_group.status = "生成失敗：答案生成器RE"
                    log(gen_out.stderr)
                    break
                tools.write(gen_out.stdout, in_file)
            cur.append(objs.Testcase(in_file=name + ".in", out_file=name + ".out", sample=False, pretest=False,
                                     group=gen_group.group))
        else:
            gen_group.status = "生成成功"
            gen_list.extend(cur)
    log(f"generate complete")
    problem.testcases_gen = gen_list


@background_actions.bind
def creating_version(pid: str, description: str):
    log(f"creating version {description!r}")
    env = executing.Environment()
    env.send_file(testlib, env.executable)
    problem.check_missing(problem.checker_source, "checker")
    file = problem.compile_dat(problem.checker_source, "checker", env)
    env.get_file(problem.path / file.inner, file)
    problem.checker = objs.ExecPtr(name=str(file.inner), lang=problem.lang_of(problem.checker_source).branch)
    if problem.is_interact:
        interactor = objs.ProgramPtr(type=objs.ProgramType.my, name=problem.interactor_source)
        problem.check_missing(interactor, "interactor")
        file = problem.compile_dat(interactor, "interactor", env)
        env.get_file(problem.path / file.inner, file)
        problem.interactor = objs.ExecPtr(name=str(file.inner), lang=problem.lang_of(interactor).branch)
    if problem.codechecker_mode != objs.CodecheckerMode.disabled:
        codechecker = objs.ProgramPtr(type=objs.ProgramType.my, name=problem.codechecker_source)
        problem.check_missing(codechecker, "codechecker")
        file = problem.compile_dat(codechecker, "codechecker", env)
        env.get_file(problem.path / file.inner, file)
        problem.codechecker = objs.ExecPtr(name=str(file.inner), lang=problem.lang(problem.codechecker_source).branch)
    if problem.gen_groups:
        generate_testcase(pid)
    problem.versions.append(objs.ProblemVersion(description=description, time=time.time()))
    target = problem_path / pid
    if target.is_dir():
        log("remove old version")
        shutil.rmtree(target)
    problem.save()  # 勿刪，此用於保證複製過去的文件完整
    log("copy overall folder")
    shutil.copytree(problem.path, target, dirs_exist_ok=True)
    log("complete")


@background_actions.bind
def do_import_polygon(pid: str, filename: str):
    zip_file = AESZipFile(filename, "r")
    filelist: list[AESZipInfo] = zip_file.filelist
    files: dict[str, AESZipInfo] = {o.filename: o for o in filelist if not o.is_dir()}
    if "problem.xml" not in files:
        abort(400)
    root: Element = ElementTree.fromstring(zip_file.read(files["problem.xml"]).decode())
    dat = problem
    path = problem.path
    dat.name = root.find("names").find("name").get("value")
    testset = root.find("judging").find("testset")
    tl = testset.find("time-limit").text
    dat.timelimit = str(max(250, min(10000, int(tl))))
    ml = testset.find("memory-limit").text
    dat.memorylimit = str(max(4, min(1024, int(ml) // 1048576)))
    groups = {"default": objs.TestcaseGroup(score=0)}
    if testset.find("groups"):
        for gp in testset.find("groups").iter("group"):
            name = gp.get("name")
            score = float(gp.get("points"))
            dependency = [e.get("group") for e in gp.iter("dependency")]
            groups[name] = {"score": score, "dependency": dependency}
    dat.groups = groups
    manual_tests = iter([files[k] for k in files if k.startswith("tests/")])
    gen_cmds = []
    if testset.find("tests"):
        for test in testset.find("tests").iter("test"):
            group = test.get("group", "default")
            if test.get("method") == "manual":
                f = next(manual_tests)
                fn = Path(f.filename).name
                tools.write_binary(zip_file.read(f), path / "testcases" / fn)
                dat.testcases.append(objs.Testcase(in_file=fn, out_file=fn + ".out", group=group, uncompleted=True))
            else:
                gen_cmds.append([test.get("cmd"), group])
    logger.debug(str(gen_cmds))
    assets = root.find("assets")
    checker = assets.find("checker").find("source")
    fn = "checker_" + Path(checker.get("path")).name
    tools.write_binary(zip_file.read(files[checker.get("path")]), path / "file" / fn)
    dat.checker_source = objs.ProgramPtr(type=objs.ProgramType.my, name=fn)
    nw_files: list[objs.ProgramFile] = [objs.ProgramFile(name=fn,
                                                         type=constants.polygon_type.get(checker.get("type"),
                                                                                         constants.default_lang))]
    interactor = assets.find("interactor")
    if interactor:
        source = interactor.find("source")
        fn = "interactor_" + Path(source.get("path")).name
        tools.write_binary(zip_file.read(files[source.get("path")]), path / "file" / fn)
        dat.interactor_source = fn
        nw_files.append(objs.ProgramFile(name=fn, type=constants.polygon_type.get(checker.get("type"),
                                                                                  constants.default_lang)))
        dat.is_interact = True
    main_sol = None
    for solution in assets.find("solutions").iter("solution"):
        source = solution.find("source")
        fn = "solution_" + Path(source.get("path")).name
        tools.write_binary(zip_file.read(files[source.get("path")]), path / "file" / fn)
        nw_files.append(objs.ProgramFile(name=fn, type=constants.polygon_type.get(checker.get("type"),
                                                                                  constants.default_lang)))
        if solution.get("tag") == "main":
            main_sol = fn
        logger.debug(source.get("path") + " " + solution.get("tag"))
    for executable in root.iter("executable"):
        source = executable.find("source")
        fn = Path(source.get("path")).name
        tools.write_binary(zip_file.read(files[source.get("path")]), path / "file" / fn)
        nw_files.append(objs.ProgramFile(name=fn, type=constants.polygon_type.get(checker.get("type"),
                                                                                  constants.default_lang)))
    for o in nw_files:
        for old in dat.files:
            if old.name == o.name:
                dat.files.remove(old)
        dat.files.append(o)
    if main_sol:
        mp = {}
        for cmd, group in gen_cmds:
            if cmd is None:
                continue
            cmdl = cmd.split()
            gen = cmdl[0]
            cmd = " ".join(cmdl[1:])
            for file in dat.files:
                if Path(file.name).stem == gen:
                    gen = file.name
                    break
            else:
                continue
            key = (gen, group)
            if key not in mp:
                mp[key] = []
            mp[key].append(cmd)
        for k, v in mp.items():
            gen, group = k
            dat.gen_groups.append(objs.GenGroup(file1=gen, file2=main_sol, group=group, type=objs.GenType.sol,
                                                cmds=v, status="未更新"))
        # dat["ex_gen_msg"] = {"solution": main_sol, "cmds": gen_cmds}
    """
    fake_form = {k: "" for k in constants.polygon_statment}
    fake_form["samples"] = "[]"
    for k, v in constants.polygon_statment.items():
        if v in files:
            fake_form[k] = zip_file.read(files[v]).decode()
    fake_form["statement_type"] = "latex"
    save_statement(fake_form, pid, path, dat)
    """
    os.remove(filename)


def runner():
    global current_pid, current_idx, problem
    while True:
        action_data = worker_queue.get()
        try:
            logger.info(f"{action_data=}")
            action_name = action_data.pop("action")
            current_idx = -1
            if "idx" in action_data:
                current_idx = action_data.pop("idx")
            current_pid = action_data["pid"]
            # time.sleep(1)
            log("start " + action_name)
            with datas.SessionContext():
                with Problem(current_pid) as problem:
                    background_actions.call(action_name, **action_data)
            end(True)
        except StopActionException:
            logger.debug("Stop Action")
        except Exception as e:
            traceback.print_exception(e)
            try:
                end(False)
            except StopActionException:
                pass
        os.chdir(root_folder)


def add_background_action(obj: dict):
    folder = preparing_problem_path / obj['pid'] / "actions"
    if not folder.is_dir():
        folder.mkdir(parents=True, exist_ok=True)
    cntfile = preparing_problem_path / obj['pid'] / "background_action_cnt"
    cnt = int(tools.read_default(cntfile, default="0"))
    idx = cnt + 1
    tools.write(str(idx), cntfile)
    obj["idx"] = idx
    worker_queue.put(obj)
    cur = obj | {"completed": False}
    tools.write_json(cur, folder / f"{idx}.json")


def check_background_action(pid: str):
    cntfile = preparing_problem_path / pid / "background_action_cnt"
    idx = tools.read_default(cntfile, default="0")
    if idx == "0":
        return None
    path = preparing_problem_path / pid / "actions"
    dat = tools.read_json(path / f"{idx}.json")
    if dat["completed"]:
        return None
    return tools.read(path / f"{idx}.log"), dat["action"]


@actions.default
def action_not_found(*args):
    abort(404)


@actions.bind
def save_general_info(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    dat.name = form["title"]
    ml = form["memorylimit"]
    tl = form["timelimit"]
    show_testcase = form["show_testcase"]
    show_checker = form["show_checker"]
    if not ml.isdigit() or not tl.isdigit():
        abort(400)
    if not (10000 >= int(tl) >= 250 and 1024 >= int(ml) >= 4):
        abort(400)
    if show_testcase not in ("yes", "no"):
        abort(400)
    if show_checker not in ("yes", "no"):
        abort(400)
    dat.memorylimit = ml
    dat.timelimit = tl
    dat.public_testcase = show_testcase == "yes"
    dat.public_checker = show_checker == "yes"
    return "general_info"


@actions.bind
def create_version(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    description = form["description"]
    add_background_action({"action": "creating_version", "pid": dat.pid, "description": description})
    return "versions"


@actions.bind
def save_statement(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    dat.manual_samples = [objs.ManualSample(*o) for o in tools.form_json(form["samples"])]
    dat.statement.main = form["statement_main"]
    dat.statement.input = form["statement_input"]
    dat.statement.output = form["statement_output"]
    dat.statement.interaction = form["statement_interaction"]
    dat.statement.scoring = form["statement_scoring"]
    dat.statement.note = form["statement_note"]
    dat.statement.type = objs.StatementType[form.get("statement_type", "md")]
    render_statement(dat)
    return "statement"


def render_statement(dat: Problem):
    obj: objs.Statement = dataclasses.replace(dat.statement)
    if obj.type == objs.StatementType.latex:
        obj.main, obj.input, obj.output, obj.interaction, obj.scoring, obj.note = \
            createhtml.run_latex(dat.pid,
                                 [obj.main, obj.input, obj.output, obj.interaction, obj.scoring, obj.note])
    full = "# 題目敘述\n" + obj.main
    if obj.input:
        full += "\n## 輸入說明\n" + obj.input
    if obj.output:
        full += "\n## 輸出說明\n" + obj.output
    if obj.interaction:
        full += "\n## 互動說明\n" + obj.interaction
    if obj.scoring:
        full += "\n## 配分\n" + obj.scoring
    if obj.note:
        full += "\n## Note\n" + obj.note
    tools.write(full, dat.path / "statement.md")
    createhtml.parse.dirname = dat.pid
    tools.write(createhtml2.run_markdown(full), dat.path / "statement.html")


@make_important
@actions.bind
def upload_zip(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    input_ext = form["input_ext"]
    output_ext = form["output_ext"]
    file = request.files["zip_file"]
    with TempFile(".zip") as tmpf:
        filepath = tmpf.path
        file.save(filepath)
        zip_file = AESZipFile(filepath, "r")
        files: list[AESZipInfo] = zip_file.filelist
        filelist = [o for o in files if not o.is_dir()]
        mp = {}
        for o in filelist:
            if o.filename.endswith(input_ext):
                mp[o.filename[:-len(input_ext)] + output_ext] = o
        ps = []
        for o in filelist:
            if o.filename in mp:
                ps.append((mp[o.filename], o))
        if len(ps) == 0:
            abort(400)
        fps = [(o.in_file, o.out_file) for o in dat.testcases]
        testcases = dat.path / "testcases"
        for o in ps:
            f0 = secure_filename(o[0].filename)
            f1 = secure_filename(o[1].filename)
            tools.write_binary(zip_file.read(o[0]), testcases / f0)
            tools.write_binary(zip_file.read(o[1]), testcases / f1)
            if (f0, f1) not in fps:
                dat.testcases.append(objs.Testcase(in_file=f0, out_file=f1, sample="sample" in f0,
                                                   pretest="pretest" in f0))
    return "tests"


@actions.bind
def upload_testcase(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    input_name = secure_filename(form["input_name"])
    output_name = secure_filename(form["output_name"])
    if input_name == "" or output_name == "":
        abort(400)
    input_path = dat.path / "testcases" / input_name
    output_path = dat.path / "testcases" / output_name
    input_content = form["input_content"]
    output_content = form["output_content"]
    if input_path.exists() or output_path.exists():
        abort(409)
    with input_path.open("w") as f:
        f.write(input_content)
    with output_path.open("w") as f:
        f.write(output_content)
    dat.testcases.append(objs.Testcase(in_file=input_name, out_file=output_name, sample=False, pretest=False))
    return "tests"


@actions.bind
def remove_testcase(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    idx = tools.to_int(form["idx"])
    if idx < 0 or idx >= len(dat.testcases):
        abort(400)
    obj = dat.testcases.pop(idx)
    (dat.path / "testcases" / obj.in_file).unlink()
    (dat.path / "testcases" / obj.out_file).unlink()
    return "tests"


@actions.bind
def upload_public_file(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    get_files = request.files.getlist("files")
    for file in get_files:
        fn = secure_filename(file.filename)
        if fn == "":
            abort(400)
        if len(fn) > 100:
            abort(400)
        if (dat.path / "public_file" / fn).exists():
            abort(409)
    for file in get_files:
        fn = secure_filename(file.filename)
        file.save(dat.path / "public_file" / fn)
    return "files"


@actions.bind
def remove_public_file(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    filename = form["filename"]
    filepath = dat.path / "public_file" / secure_filename(filename)
    if filepath.is_file():
        filepath.unlink()
    else:
        abort(404)
    return "files"


@actions.bind
def upload_file(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    get_files = request.files.getlist("files")
    for file in get_files:
        fn = secure_filename(file.filename)
        if fn == "":
            abort(400)
        if len(fn) > 100:
            abort(400)
        if (dat.path / "file" / fn).exists():
            abort(409)
        file.save(dat.path / "file" / fn)
        ext = Path(fn).suffix
        tp = constants.default_lang
        for lang in executing.langs.values():
            if ext == lang.source_ext:
                tp = lang.data["default_branch"]
                break
        dat.files.append(objs.ProgramFile(name=fn, type=tp))
    return "files"


@actions.bind
def create_file(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    filename = secure_filename(form["filename"])
    if len(filename) == 0 or len(filename) > 100:
        abort(400)
    filepath = dat.path / "file" / filename
    if filepath.exists():
        abort(409)
    filepath.touch()
    dat.files.append(objs.ProgramFile(name=filename, type=constants.default_lang))
    return "files"


@actions.bind
def remove_file(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    filename = secure_filename(form["filename"])
    filepath = dat.path / "file" / filename
    target: objs.ProgramFile | None = None
    for o in dat.files:
        if o.name == filename:
            target = o
            break
    if target is None:
        abort(404)
    if filepath.exists():
        filepath.unlink()
    else:
        abort(400)
    dat.files.remove(target)
    return "files"


@actions.bind
def save_file_content(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    filename = form["filename"]
    filename = secure_filename(filename)
    content = form["content"]
    if form["type"] not in executing.langs:
        abort(400)
    filepath = dat.path / "file" / filename
    target: objs.ProgramFile | None = None
    for o in dat.files:
        if o.name == filename:
            target = o
            break
    if target is None:
        abort(404)
    target.type = form["type"]
    tools.write(content, Path(filepath))
    return "files"


@actions.bind
def choose_checker(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    tp = form["checker_type"]
    if tp not in ("my", "default"):
        abort(400)
    name = secure_filename(form[tp + "_checker"])
    filepath = (Path("testlib/checkers") if tp == "default" else dat.path / "file") / name
    if not filepath.is_file():
        abort(400)
    dat.checker_source = objs.ProgramPtr(type=ProgramType[tp], name=name)
    return "judge"


@actions.bind
def choose_interactor(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    tp = "my"
    name = secure_filename(form[tp + "_interactor"])
    use = form.get("enable_interactor", "off") == "on"
    if not any(o.name == name for o in dat.files):
        dat.is_interact = False
        dat.interactor_source = "unknown"
    else:
        dat.interactor_source = name
        dat.is_interact = use
    return "judge"


@actions.bind
def choose_codechecker(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    name = secure_filename(form["my_codechecker"])
    mode = form["codechecker_mode"]
    if not any(o.name == name for o in dat.files):
        mode = "disabled"
        name = "unknown"
    if mode not in ("disabled", "public", "private"):
        mode = "disabled"
    dat.codechecker_mode = objs.CodecheckerMode[mode]
    dat.codechecker_source = name
    return "judge"


@actions.bind
def choose_runner(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    use = form.get("enable_runner", "off") == "on"
    for k in executing.langs.keys():
        name = secure_filename(form["my_runner_" + k])
        if not any(o.name == name for o in dat.files):
            if k in dat.runner_source:
                del dat.runner_source[k]
        else:
            dat.runner_source[k] = name
    dat.runner_enabled = use
    return "judge"


@actions.bind
def add_library(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    name = form["library"]
    if not any(o.name == name for o in dat.files):
        abort(404)
    elif name in dat.library:
        abort(409)
    else:
        dat.library.append(name)
    return "judge"


@actions.bind
def remove_library(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    name = form["name"]
    if name not in dat.library:
        abort(409)
    else:
        dat.library.remove(name)
    return "judge"


@actions.bind
def save_testcase(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    try:
        modify = json.loads(form["modify"])
    except json.decoder.JSONDecodeError:
        abort(400)
    testcases = dat.testcases
    if type(modify) is not list or len(modify) != len(testcases):
        abort(400)
    s = set()
    new_testcases = []
    for o in modify:
        if (len(o) < 4 or
                type(o[1]) is not bool or
                type(o[0]) is not int or
                not (len(testcases) > o[0] >= 0) or
                o[3] not in dat.groups):
            abort(400)
        if o[0] in s:
            abort(400)
        s.add(o[0])
        obj = testcases[o[0]]
        obj.sample = o[1]
        obj.pretest = o[2]
        obj.group = o[3]
        new_testcases.append(obj)
    dat.testcases = new_testcases
    return "tests"


@actions.bind
def do_generate(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    add_background_action({"action": "generate_testcase", "pid": dat.pid})
    return "tests"


@actions.bind
def create_group(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    name = secure_filename(form["name"].strip())
    if name in dat.groups:
        abort(409)
    dat.groups[name] = objs.TestcaseGroup()
    return "tests"


@actions.bind
def remove_group(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    name = secure_filename(form["name"])
    if name not in dat.groups:
        abort(404)
    if name == "default":
        abort(400)
    del dat.groups[name]
    for o in dat.testcases:
        if o.group == name:
            o.group = "default"
    return "tests"


@actions.bind
def save_groups(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    d = {}
    dr = {}
    for k in dat.groups:
        if not form["score_" + k].isdigit():
            abort(400)
        if form["rule_" + k] not in ("min", "avg"):
            abort(400)
        d[k] = int(form["score_" + k])
        dr[k] = form["rule_" + k]
    cnt = len(dat.groups)
    names = list(dat.groups.keys())
    dep = {i: [] for i in range(cnt)}
    for i in range(cnt):
        for j in range(cnt):
            if f"dependency_{i}_{j}" in form:
                if i == j:
                    abort(400)
                dep[i].append(j)
    order = list(range(cnt))
    try:
        order = list(TopologicalSorter(dep).static_order())
    except CycleError:
        abort(400)
    for i, k in enumerate(dat.groups):
        dat.groups[k].score = d[k]
        dat.groups[k].rule = objs.TestcaseRule[dr[k]]
        dat.groups[k].dependency = [names[j] for j in dep[i]]
    tmp = []
    for k, v in dat.groups.items():
        tmp.append((k, v))
    dat.groups.clear()
    for i in order:
        dat.groups[tmp[i][0]] = tmp[i][1]
    return "tests"


@actions.bind
def protect_problem(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    if not dat.sql_data.is_public:
        abort(400)
    dat.sql_data.is_public = False
    return "general_info"


@actions.bind
def public_problem(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    if dat.sql_data.is_public:
        abort(400)
    if len(dat.versions) == 0:
        abort(409)
    dat.sql_data.is_public = True
    return "general_info"


@actions.bind
def save_languages(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    for k in executing.langs.keys():
        mul = form.get("lang_mul_" + k, "1")
        if not mul.isdigit() or int(mul) < 1 or int(mul) > 100:
            abort(400)
    for k in executing.langs.keys():
        dat.languages[k] = (form.get("lang_check_" + k, "off") == "on")
        dat.language_multipliers[k] = int(form.get("lang_mul_" + k, "1"))
    return "languages"


def prepare_gen_group(form: ImmutableMultiDict[str, str], dat: Problem):
    file1 = form["file1"]
    if not any(o.name == file1 for o in dat.files):
        abort(404)
    file2 = form["file2"]
    if not any(o.name == file2 for o in dat.files):
        abort(404)
    group = form["group"]
    if group not in dat.groups:
        abort(404)
    tp = form["type"]
    if tp not in ("sol", "gen"):
        abort(400)
    return file1, file2, group, objs.GenType[tp]


@actions.bind
def create_gen_group(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    file1, file2, group, tp = prepare_gen_group(form, dat)
    cnt = tools.to_int(form["mul"])
    cmds = form["cmds"].split("\n")
    out_cmds = []
    for i in range(1, cnt + 1):
        for s in cmds:
            out_cmds.append(s.replace("{index}", str(i)))
    dat.gen_groups.append(objs.GenGroup(file1=file1, file2=file2, group=group, type=tp, cmds=out_cmds, status="未更新"))
    return "tests"


@actions.bind
def update_gen_group(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    file1, file2, group, tp = prepare_gen_group(form, dat)
    idx = tools.to_int(form["idx"])
    cmds = form["cmds"].split("\n")
    if idx < 0 or idx >= len(dat.gen_groups):
        abort(400)
    dat.gen_groups[idx] = objs.GenGroup(file1=file1, file2=file2, group=group, type=tp, cmds=cmds, status="未更新")
    return "tests"


@actions.bind
def remove_gen_group(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    idx = tools.to_int(form["idx"])
    if idx < 0 or idx >= len(dat.gen_groups):
        abort(400)
    dat.gen_groups.pop(idx)
    return "tests"


@actions.bind
def import_polygon(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    file = request.files["zip_file"]
    filename = str(TempFile(".zip").path)
    file.save(filename)
    add_background_action({"action": "do_import_polygon", "pid": dat.pid, "filename": filename})
    return "import"


@actions.bind
def import_problem(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    zip_file = request.files["zip_file"]
    with TempFile(".zip") as tmp:
        zip_file.save(tmp.path)
        dirs = ("file", "public_file", "testcases")
        files = ("statement.html", "statement.md")
        with AESZipFile(tmp.path, "r") as zf:
            for file in zf.filelist:
                file: AESZipInfo
                if file.filename in files:
                    zf.extract(file, dat.path)
                elif file.filename == "info.json":
                    users = dat.users
                    public_testcase = dat.public_testcase
                    dat.update(json.loads(zf.read(file).decode()))
                    dat.users = users
                    dat.public_testcase = public_testcase
                else:
                    dir_name = Path(file.filename).parent.name
                    if dir_name in dirs:
                        zf.extract(file, dat.path)
    render_statement(dat)
    return "import"


@actions.bind
def export_problem(form: ImmutableMultiDict[str, str], dat: Problem) -> str | Response:
    filename = tmp_path / f"{tools.random_string()}.zip"
    dirs = ("file", "public_file", "testcases")
    files = ("statement.html", "statement.md")
    with AESZipFile(filename, "w") as zf:
        for name in dirs:
            f: Path
            for f in (dat.path / name).iterdir():
                zf.write(f, f.relative_to(dat.path))
        for f in files:
            zf.write(dat.path / f, f)
        zf.writestr("info.json", json.dumps(objs.as_dict(dat), indent=4))
    return sending_file(filename)


def action(form: ImmutableMultiDict[str, str]) -> Response:
    pid = secure_filename(form["pid"])
    func = actions.get(form["action"])
    important = hasattr(func, "important") and getattr(func, "important")
    with Problem(pid, important) as dat:
        tp = actions.call(form["action"], form, dat)
        if type(tp) is str:
            return redirect(f"/problemsetting/{pid}#{tp}")
        else:
            return tp


def preview(args: MultiDict[str, str], pdat: datas.Problem) -> Response:
    pid = args["pid"]
    path = preparing_problem_path / pid

    def filename():
        return secure_filename(args["name"])

    match args["type"]:
        case "statement":
            if not (path / "statement.html").exists():
                abort(404)
            dat = pdat.new_datas
            langs = [lang for lang in executing.langs.keys() if pdat.lang_allowed(lang)]
            return render_problem(dat, pid, langs, preview=True, is_contest=False)
        case "public_file":
            return sending_file(path / "public_file" / filename())
        case "file":
            return sending_file(path / "file" / filename())
        case "testcases":
            return sending_file(path / "testcases" / filename())
        case "testcases_gen":
            return sending_file(path / "testcases_gen" / filename())
    abort(404)


def query_versions(pdat: datas.Problem):
    out = []
    info = pdat.new_datas
    for o in info.versions:
        out.append({
            "date": str(int(float(o.time))),
            "message": o.description
        })
    out.reverse()
    for i, o in enumerate(out):
        o["id"] = str(len(out) - i - 1)
    return out
