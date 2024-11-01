import datetime
import json
import os
import shutil
import time
import traceback
from graphlib import TopologicalSorter, CycleError
from multiprocessing import Queue, Process
from typing import Callable
from xml.etree import ElementTree
from xml.etree.ElementTree import Element

from flask import Response, abort, render_template, request, redirect, send_file
from pyzipper import AESZipFile
from pyzipper.zipfile_aes import AESZipInfo
from sqlalchemy.orm.attributes import flag_modified
from werkzeug.datastructures import ImmutableMultiDict, MultiDict
from werkzeug.utils import secure_filename

from modules import executing, tools, constants, createhtml, datas

worker_queue = Queue()

root_folder = os.getcwd()
background_actions = tools.Switcher()
actions = tools.Switcher()
current_pid = ""
current_idx = 0


def make_important(func: Callable) -> Callable:
    func.important = True
    return func


class StopActionException(Exception):
    pass


def just_compile(path: str, name: str, lang: executing.Language, env: executing.Environment) -> str:
    log(f"compile {name} ({os.path.basename(path)})")
    file = env.send_file(path)
    exec_file, ce_msg = lang.compile(file, env)
    if ce_msg:
        log(f"{name} CE")
        log(ce_msg)
        end(False)
    return exec_file


def do_compile(path: str, name: str, lang: executing.Language, env: executing.Environment) -> list[str]:
    return lang.get_execmd(just_compile(path, name, lang, env))


class Problem:
    def __init__(self, pid: str, is_important_editing_now: bool = True):
        self.pid = pid
        self.path = "preparing_problems/" + pid
        self.is_important_editing_now = is_important_editing_now
        self.sql_data: datas.Problem = datas.Problem.query.filter_by(pid=pid).first()
        if self.is_important_editing_now:
            self.sql_data.editing = True
            datas.add(self.sql_data)
        self.dat = self.sql_data.new_data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.sql_data.new_data = self.dat
        self.sql_data.name = self.dat["name"]
        flag_modified(self.sql_data, "new_data")
        if self.is_important_editing_now:
            self.sql_data.editing = False
            self.sql_data.edit_time = datetime.datetime.now()
        datas.add(self.sql_data)

    def save(self):
        self.sql_data.data = self.sql_data.new_data
        flag_modified(self.sql_data, "data")
        datas.add(self.sql_data)

    def __getitem__(self, item):
        if item not in self.dat and item in constants.default_problem_info:
            return constants.default_problem_info[item]
        return self.dat[item]

    def __setitem__(self, key, value):
        self.dat[key] = value

    def __contains__(self, item):
        return item in self.dat

    def get(self, item, value):
        return self.dat.get(item, value)

    def lang(self, name) -> executing.Language:
        fs = [o["type"] for o in self.dat["files"] if o["name"] == name]
        if len(fs):
            return executing.langs[fs[0]]
        else:
            log(f"file {name} not found")
            end(False)

    def lang_of(self, tp, name) -> executing.Language:
        if tp == "default":
            return executing.langs["C++17"]
        fs = [o["type"] for o in self.dat["files"] if o["name"] == name]
        if len(fs):
            return executing.langs[fs[0]]
        else:
            log(f"file {name} not found")
            end(False)

    def compile_inner(self, filename: str, name: str, env: executing.Environment) -> list[str]:
        lang = self.lang(filename)
        path = self.path + "/file/" + filename
        return do_compile(path, name, lang, env)

    def compile_dat(self, filedat: tuple[str, str], name: str, env: executing.Environment) -> str:
        path = os.path.join(f"testlib/{name}s" if filedat[0] == "default" else f"{self.path}/file", filedat[1])
        lang = executing.langs["C++17"] if filedat[0] == "default" else self.lang(filedat[1])
        return just_compile(path, name, lang, env)


problem: Problem | None = None


def init() -> None:
    global root_folder
    root_folder = os.path.abspath(os.getcwd())
    Process(target=runner).start()


def create_problem(name: str, pid: str, user: datas.User) -> str:
    pcnt = datas.Problem.query.count()
    if len(name) == 0 or len(name) > 120:
        abort(400)
    if pid:
        if constants.problem_id_reg.match(pid) is None:
            abort(400)
        if datas.Problem.query.filter_by(pid=pid).count():
            abort(409)
    else:
        pidx = pcnt + 1000
        while datas.Problem.query.filter_by(pid=str(pidx)).count():
            pidx += 1
        pid = str(pidx)
    dat = datas.Problem(id=pcnt + 1, pid=pid, name=name, data={}, user=user)
    path = "preparing_problems/" + pid
    os.mkdir(path)
    try:
        making_dir(path + "/testcases")
        making_dir(path + "/file")
        making_dir(path + "/public_file")
    except FileExistsError:
        pass
    info = constants.default_problem_info | {"name": name, "users": [user.username]}
    dat.data = dat.new_data = info
    datas.add(dat)
    return pid


def making_dir(path: str):
    os.makedirs(path, exist_ok=True)
    tools.create(path, ".gitkeep")


def log(s: str, success: bool | None = None):
    tools.log(s)
    if not s.endswith("\n"):
        s += "\n"
    tools.append(s, f"preparing_problems/{current_pid}/actions/{current_idx}.log")
    if type(success) is bool:
        end(success)


def end(success: bool):
    with tools.Json(f"preparing_problems/{current_pid}/actions/{current_idx}.json") as dat:
        dat["success"] = success
        dat["completed"] = True
    raise StopActionException()


@background_actions.bind
def generate_testcase(pid: str):
    log(f"generating testcase")
    path = "preparing_problems/" + pid
    env = executing.Environment()
    env.send_file("testlib/testlib.h")
    gen_list = []
    int_cmd = []
    run_cmds = {}

    def get_cmd(s: str, title: str):
        if s not in run_cmds:
            run_cmds[s] = problem.compile_inner(s, title, env)
        return run_cmds[s]

    if problem["is_interact"]:
        int_cmd = get_cmd(problem["interactor_source"], "interactor")
    tl = float(problem["timelimit"]) / 1000
    ml = int(problem["memorylimit"])
    log("clear folder")
    shutil.rmtree(f"{path}/testcases_gen")
    os.makedirs(f"{path}/testcases_gen")
    log("complete clear folder")
    if "gen_groups" in problem:
        for gpidx, gen_group in enumerate(problem["gen_groups"]):
            file1_cmd = get_cmd(gen_group["file1"], "generator")
            file2_cmd = get_cmd(gen_group["file2"], "solution" if gen_group['type'] == "sol" else "ans_generator")
            sol_lang = problem.lang(gen_group["file2"])
            cur = []
            for tcidx, cmd in enumerate(gen_group['cmds']):
                name = f"{gpidx}_{tcidx}"
                in_file = os.path.abspath(f"{path}/testcases_gen/{name}.in")
                out_file = os.path.abspath(f"{path}/testcases_gen/{name}.out")
                log(f"generating testcase {name!r}")
                gen_out = env.safe_run(file1_cmd + cmd.split())
                if gen_out[2]:
                    log("generator RE")
                    gen_group['status'] = "生成失敗：生成器RE"
                    log(gen_out[1])
                    break
                tools.write(gen_out[0], in_file)
                if gen_group['type'] == "sol":
                    env.send_file(in_file)
                    if problem["is_interact"]:
                        env.judge_readable(in_file)
                        env.judge_writeable(out_file)
                        out = env.runwithinteractshell(file2_cmd, int_cmd, env.filepath(in_file),
                                                       env.filepath(out_file),
                                                       tl, ml,
                                                       sol_lang.base_exec_cmd)
                    else:
                        out = env.runwithshell(file2_cmd, env.filepath(in_file), env.filepath(out_file), tl, ml,
                                               sol_lang.base_exec_cmd)
                    if executing.is_tle(out):
                        log("solution TLE")
                        gen_group['status'] = "生成失敗：官解TLE"
                        log(out[1])
                        break
                    result = {o[0]: o[1] for o in (s.split("=") for s in out[0].split("\n")) if len(o) == 2}
                    if "1" == result.get("WIFSIGNALED", None) or "0" != result.get("WEXITSTATUS", "0"):
                        log("solution RE")
                        gen_group['status'] = "生成失敗：官解RE"
                        log(out[1])
                        break
                    if "time" in result and float(result["time"]) >= 0:
                        timeusage = int((float(result["time"]) + float(result["basetime"])) * 1000)
                        if timeusage > tl * 950:
                            gen_group['status'] = "生成失敗：官解TLE"
                    if "mem" in result and float(result["mem"]) >= 0:
                        memusage = (int(result["mem"]) - int(result["basemem"])) * int(result["pagesize"]) // 1000
                        if memusage > ml * 1024:
                            gen_group['status'] = "生成失敗：官解MLE"
                    env.get_file(out_file)
                else:
                    gen_out = env.safe_run(file2_cmd + cmd.split())
                    if gen_out[2]:
                        log("generator RE")
                        gen_group['status'] = "生成失敗：答案生成器RE"
                        log(gen_out[1])
                        break
                    tools.write(gen_out[0], in_file)
                cur.append({"in": name + ".in", "out": name + ".out", "sample": False, "pretest": False,
                            "group": gen_group['group']})
            else:
                gen_group['status'] = "生成成功"
                gen_list.extend(cur)
    log(f"generate complete")
    problem["testcases_gen"] = gen_list


@background_actions.bind
def creating_version(pid: str, description: str):
    path = "preparing_problems/" + pid
    log(f"creating version {description!r}")
    env = executing.Environment()
    env.send_file("testlib/testlib.h")
    if "checker_source" not in problem:
        log("checker missing")
        end(False)
    file = problem.compile_dat(problem["checker_source"], "checker", env)
    env.get_file(path + "/" + os.path.basename(file), os.path.basename(file))
    problem["checker"] = [os.path.basename(file), problem.lang_of(*problem["checker_source"]).branch]
    if problem["is_interact"]:
        if "interactor_source" not in problem:
            log("interactor missing")
            end(False)
        file = problem.compile_dat(("my", problem["interactor_source"]), "interactor", env)
        env.get_file(path + "/" + os.path.basename(file), file)
        problem["interactor"] = [os.path.basename(file), problem.lang(problem["interactor_source"]).branch]
    if "gen_msg" in problem or "ex_gen_msg" in problem:
        generate_testcase(pid)
    if "versions" not in problem:
        problem["versions"] = []
    problem["versions"].append({"description": description, "time": time.time()})
    if os.path.exists("problems/" + pid):
        log("remove old version")
        shutil.rmtree("problems/" + pid)
    problem.save()  # 勿刪，此用於保證複製過去的文件完整
    log("copy overall folder")
    shutil.copytree(path, "problems/" + pid, dirs_exist_ok=True)
    log("complete")


@background_actions.bind
def do_import_polygon(pid: str, filename: str):
    zip_file = AESZipFile(filename, "r")
    filelist: list[AESZipInfo] = zip_file.filelist
    files: dict[str, AESZipInfo] = {o.filename: o for o in filelist if not o.is_dir()}
    if "problem.xml" not in files:
        abort(400)
    root: Element = ElementTree.fromstring(zip_file.read(files["problem.xml"]).decode())
    path = f"preparing_problems/{pid}"
    dat = problem
    dat["name"] = root.find("names").find("name").get("value")
    testset = root.find("judging").find("testset")
    tl = testset.find("time-limit").text
    dat["timelimit"] = str(max(250, min(10000, int(tl))))
    ml = testset.find("memory-limit").text
    dat["memorylimit"] = str(max(4, min(1024, int(ml) // 1048576)))
    groups = {"default": {"score": 0}}
    if testset.find("groups"):
        for gp in testset.find("groups").iter("group"):
            name = gp.get("name")
            score = float(gp.get("points"))
            dependency = [e.get("group") for e in gp.iter("dependency")]
            groups[name] = {"score": score, "dependency": dependency}
    dat["groups"] = groups
    manual_tests = iter([files[k] for k in files if k.startswith("tests/")])
    gen_cmds = []
    if testset.find("tests"):
        for test in testset.find("tests").iter("test"):
            group = test.get("group", "default")
            if test.get("method") == "manual":
                f = next(manual_tests)
                fn = os.path.basename(f.filename)
                tools.write_binary(zip_file.read(f), path, "testcases", fn)
                dat["testcases"].append({"in": fn, "out": fn + ".out", "group": group, "uncomplete": True})
            else:
                gen_cmds.append([test.get("cmd"), group])
    tools.log(gen_cmds)
    assets = root.find("assets")
    checker = assets.find("checker").find("source")
    fn = "checker_" + os.path.basename(checker.get("path"))
    tools.write_binary(zip_file.read(files[checker.get("path")]), path, "file", fn)
    dat["checker_source"] = ["my", fn]
    nw_files = [{"name": fn, "type": constants.polygon_type.get(checker.get("type"), "C++17")}]
    interactor = assets.find("interactor")
    if interactor:
        source = interactor.find("source")
        fn = "interactor_" + os.path.basename(source.get("path"))
        tools.write_binary(zip_file.read(files[source.get("path")]), path, "file", fn)
        dat["interactor_source"] = fn
        nw_files.append({"name": fn, "type": constants.polygon_type.get(source.get("type"), "C++17")})
        dat["is_interact"] = True
    main_sol = None
    for solution in assets.find("solutions").iter("solution"):
        source = solution.find("source")
        fn = "solution_" + os.path.basename(source.get("path"))
        tools.write_binary(zip_file.read(files[source.get("path")]), path, "file", fn)
        nw_files.append({"name": fn, "type": constants.polygon_type.get(source.get("type"), "C++17")})
        if solution.get("tag") == "main":
            main_sol = fn
        tools.log(source.get("path"), solution.get("tag"))
    for executable in root.iter("executable"):
        source = executable.find("source")
        fn = os.path.basename(source.get("path"))
        tools.write_binary(zip_file.read(files[source.get("path")]), path, "file", fn)
        nw_files.append({"name": fn, "type": constants.polygon_type.get(source.get("type"), "C++17")})
    for o in nw_files:
        for old in dat["files"]:
            if old["name"] == o["name"]:
                dat["files"].remove(old)
        dat["files"].append(o)
    if main_sol:
        mp = {}
        for cmd, group in gen_cmds:
            if cmd is None:
                continue
            cmdl = cmd.split()
            gen = cmdl[0]
            cmd = " ".join(cmdl[1:])
            for file in dat["files"]:
                if os.path.splitext(file["name"])[0] == gen:
                    gen = file["name"]
                    break
            else:
                continue
            key = (gen, group)
            if key not in mp:
                mp[key] = []
            mp[key].append(cmd)
        if "gen_groups" not in dat:
            dat["gen_groups"] = []
        for k, v in mp.items():
            gen, group = k
            dat["gen_groups"].append({"file1": gen, "file2": main_sol, "group": group, "type": "sol", "cmds": v,
                                      "status": "未更新"})
        dat["ex_gen_msg"] = {"solution": main_sol, "cmds": gen_cmds}
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
            tools.log(f"{action_data=}")
            action_name = action_data.pop("action")
            current_idx = -1
            if "idx" in action_data:
                current_idx = action_data.pop("idx")
            current_pid = action_data["pid"]
            # time.sleep(1)
            log("start " + action_name)
            with Problem(current_pid) as problem:
                background_actions.call(action_name, **action_data)
            end(True)
        except StopActionException:
            tools.log("Stop Action")
        except Exception as e:
            traceback.print_exception(e)
            try:
                end(False)
            except StopActionException:
                pass
        os.chdir(root_folder)


def add_background_action(obj: dict):
    folder = f"preparing_problems/{obj['pid']}/actions"
    if not os.path.isdir(folder):
        os.makedirs(folder, exist_ok=True)
    cnt = int(tools.read_default(f"preparing_problems/{obj['pid']}/background_action_cnt", default="0"))
    idx = cnt + 1
    tools.write(str(idx), f"preparing_problems/{obj['pid']}/background_action_cnt")
    obj["idx"] = idx
    worker_queue.put(obj)
    cur = obj | {"completed": False}
    tools.write_json(cur, f"preparing_problems/{obj['pid']}/actions/{idx}.json")


def check_background_action(pid: str):
    idx = tools.read_default(f"preparing_problems/{pid}/background_action_cnt", default="0")
    if idx == "0":
        return None
    dat = tools.read_json(f"preparing_problems/{pid}/actions/{idx}.json")
    if dat["completed"]:
        return None
    return tools.read(f"preparing_problems/{pid}/actions/{idx}.log"), dat["action"]


@actions.default
def action_not_found(*args):
    abort(404)


@actions.bind
def save_general_info(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    dat["name"] = form["title"]
    ml = form["memorylimit"]
    tl = form["timelimit"]
    show_testcase = form["show_testcase"]
    if not ml.isdigit() or not tl.isdigit():
        abort(400)
    if not (10000 >= int(tl) >= 250 and 1024 >= int(ml) >= 4):
        abort(400)
    if show_testcase not in ("yes", "no"):
        abort(400)
    dat["memorylimit"] = ml
    dat["timelimit"] = tl
    dat["public_testcase"] = show_testcase == "yes"
    return "general_info"


@actions.bind
def create_version(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    description = form["description"]
    add_background_action({"action": "creating_version", "pid": pid, "description": description})
    return "versions"


@actions.bind
def save_statement(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    dat["manual_samples"] = tools.form_json(form["samples"])
    obj = dat["statement"]
    obj["main"] = form["statement_main"]
    obj["input"] = form["statement_input"]
    obj["output"] = form["statement_output"]
    obj["interaction"] = form["statement_interaction"]
    obj["scoring"] = form["statement_scoring"]
    obj["type"] = form.get("statement_type", "md")
    render_statement(pid, dat)
    return "statement"


def render_statement(pid: str, dat: Problem):
    obj = dat["statement"].copy()
    if obj["type"] == "latex":
        obj["main"], obj["input"], obj["output"], obj["interaction"], obj["scoring"] = \
            createhtml.run_latex(pid, [obj["main"], obj["input"], obj["output"], obj["interaction"], obj["scoring"]])
    full = "# 題目敘述\n" + obj["main"]
    if obj["input"]:
        full += "\n## 輸入說明\n" + obj["input"]
    if obj["output"]:
        full += "\n## 輸出說明\n" + obj["output"]
    if obj["interaction"]:
        full += "\n## 互動說明\n" + obj["interaction"]
    if obj["scoring"]:
        full += "\n## 配分\n" + obj["scoring"]
    tools.write(full, f"preparing_problems/{pid}/statement.md")
    createhtml.parse.dirname = pid
    tools.write(createhtml.run_markdown(full), f"preparing_problems/{pid}/statement.html")


@make_important
@actions.bind
def upload_zip(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    input_ext = form["input_ext"]
    output_ext = form["output_ext"]
    file = request.files["zip_file"]
    filename = f"tmp/{tools.random_string()}.zip"
    file.save(filename)
    zip_file = AESZipFile(filename, "r")
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
    fps = [(o["in"], o["out"]) for o in dat["testcases"]]
    if os.path.isdir(path + "/testcases/"):
        shutil.rmtree(path + "/testcases/")
        os.makedirs(path + "/testcases/", exist_ok=True)
    for o in ps:
        f0 = secure_filename(o[0].filename)
        f1 = secure_filename(o[1].filename)
        tools.write_binary(zip_file.read(o[0]), f"{path}/testcases/{f0}")
        tools.write_binary(zip_file.read(o[1]), f"{path}/testcases/{f1}")
        if (f0, f1) not in fps:
            dat["testcases"].append({"in": f0, "out": f1, "sample": "sample" in f0, "pretest": "pretest" in f0})
    os.remove(filename)
    return "tests"


@actions.bind
def upload_testcase(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    input_name = secure_filename(form["input_name"])
    output_name = secure_filename(form["output_name"])
    if input_name == "" or output_name == "":
        abort(400)
    input_content = form["input_content"]
    output_content = form["output_content"]
    for o in dat["testcases"]:
        if o["in"] == input_name or o["out"] == input_name or \
                o["in"] == output_name or o["out"] == output_name:
            abort(409)
    with open(path + "/testcases/" + input_name, "w") as f:
        f.write(input_content)
    with open(path + "/testcases/" + output_name, "w") as f:
        f.write(output_content)
    dat["testcases"].append({"in": input_name, "out": output_name, "sample": False, "pretest": False})
    return "tests"


@actions.bind
def remove_testcase(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    idx = tools.to_int(form["idx"])
    if idx < 0 or idx >= len(dat["testcases"]):
        abort(400)
    obj = dat["testcases"].pop(idx)
    os.remove(path + "/testcases/" + obj["in"])
    os.remove(path + "/testcases/" + obj["out"])
    return "tests"


@actions.bind
def upload_public_file(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    get_files = request.files.getlist("files")
    for file in get_files:
        fn = secure_filename(file.filename)
        if fn == "":
            abort(400)
        if len(fn) > 100:
            abort(400)
        if tools.exists(path, "public_file", fn):
            abort(409)
    for file in get_files:
        fn = secure_filename(file.filename)
        file.save(path + "/public_file/" + fn)
    return "files"


@actions.bind
def remove_public_file(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    filename = form["filename"]
    filepath = path + "/public_file/" + secure_filename(filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    else:
        abort(404)
    return "files"


@actions.bind
def upload_file(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    get_files = request.files.getlist("files")
    for file in get_files:
        fn = secure_filename(file.filename)
        if fn == "":
            abort(400)
        if len(fn) > 100:
            abort(400)
        if tools.exists(path, "file/", fn):
            abort(409)
        file.save(path + "/file/" + fn)
        dat["files"].append({"name": fn, "type": "C++17"})
    return "files"


@actions.bind
def create_file(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    filename = secure_filename(form["filename"])
    if len(filename) == 0 or len(filename) > 100:
        abort(400)
    if tools.exists(path, "file", filename):
        abort(409)
    tools.create(path, "file", filename)
    dat["files"].append({"name": filename, "type": "C++17"})
    return "files"


@actions.bind
def remove_file(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    filename = secure_filename(form["filename"])
    filepath = path + "/file/" + filename
    target = None
    for o in dat["files"]:
        if o["name"] == filename:
            target = o
            break
    if target is None:
        abort(404)
    if os.path.exists(filepath):
        os.remove(filepath)
    else:
        abort(400)
    dat["files"].remove(target)
    return "files"


@actions.bind
def save_file_content(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    filename = form["filename"]
    filename = secure_filename(filename)
    content = form["content"]
    if form["type"] not in executing.langs:
        abort(400)
    filepath = path + "/file/" + filename
    target = None
    for o in dat["files"]:
        if o["name"] == filename:
            target = o
            break
    if target is None:
        abort(404)
    target["type"] = form["type"]
    tools.write(content, filepath)
    return "files"


@actions.bind
def choose_checker(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    tp = form["checker_type"]
    if tp not in ("my", "default"):
        abort(400)
    name = secure_filename(form[tp + "_checker"])
    filepath = ("testlib/checkers/" if tp == "default" else path + "/file/") + name
    if not os.path.isfile(filepath):
        abort(400)
    dat["checker_source"] = [tp, name]
    return "judge"


@actions.bind
def choose_interactor(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    tp = "my"
    name = secure_filename(form[tp + "_interactor"])
    use = form.get("enable_interactor", "off") == "on"
    if not any(o["name"] == name for o in dat["files"]):
        dat["is_interact"] = False
        dat["interactor_source"] = "unknown"
    else:
        dat["interactor_source"] = name
        dat["is_interact"] = use
    return "judge"


@actions.bind
def choose_runner(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    use = form.get("enable_runner", "off") == "on"
    if "runner_source" not in dat:
        dat["runner_source"] = {}
    for k in executing.langs.keys():
        name = secure_filename(form["my_runner_" + k])
        if not any(o["name"] == name for o in dat["files"]):
            if k in dat["runner_source"]:
                del dat["runner_source"][k]
        else:
            dat["runner_source"][k] = name
    dat["runner_enabled"] = use
    return "judge"


@actions.bind
def add_library(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    if "library" not in dat:
        dat["library"] = []
    name = form["library"]
    if not any(o["name"] == name for o in dat["files"]):
        abort(404)
    elif name in dat["library"]:
        abort(409)
    else:
        dat["library"].append(name)
    return "judge"


@actions.bind
def remove_library(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    if "library" not in dat:
        dat["library"] = []
    name = form["name"]
    if name not in dat["library"]:
        abort(409)
    else:
        dat["library"].remove(name)
    return "judge"


@actions.bind
def save_testcase(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    try:
        modify = json.loads(form["modify"])
    except json.decoder.JSONDecodeError:
        abort(400)
    testcases = dat["testcases"]
    if type(modify) is not list or len(modify) != len(testcases):
        abort(400)
    s = set()
    new_testcases = []
    for o in modify:
        if (len(o) < 4 or
                type(o[1]) is not bool or
                type(o[0]) is not int or
                not (len(testcases) > o[0] >= 0) or
                o[3] not in dat["groups"]):
            abort(400)
        if o[0] in s:
            abort(400)
        s.add(o[0])
        obj = testcases[o[0]]
        obj["sample"] = o[1]
        obj["pretest"] = o[2]
        obj["group"] = o[3]
        new_testcases.append(obj)
    dat["testcases"] = new_testcases
    return "tests"


@actions.bind
def do_generate(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    add_background_action({"action": "generate_testcase", "pid": pid})
    return "tests"


@actions.bind
def create_group(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    name = secure_filename(form["name"].strip())
    if name in dat["groups"]:
        abort(409)
    dat["groups"][name] = {"score": 100, "rule": "min", "dependency": []}
    return "tests"


@actions.bind
def remove_group(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    name = secure_filename(form["name"])
    if name not in dat["groups"]:
        abort(404)
    if name == "default":
        abort(400)
    del dat["groups"][name]
    for o in dat["testcases"]:
        if o["group"] == name:
            o["group"] = "default"
    return "tests"


@actions.bind
def save_groups(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    d = {}
    dr = {}
    for k in dat["groups"]:
        if not form["score_" + k].isdigit():
            abort(400)
        if form["rule_" + k] not in ("min", "avg"):
            abort(400)
        d[k] = int(form["score_" + k])
        dr[k] = form["rule_" + k]
    cnt = len(dat["groups"])
    names = list(dat["groups"].keys())
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
    for i, k in enumerate(dat["groups"]):
        dat["groups"][k]["score"] = d[k]
        dat["groups"][k]["rule"] = dr[k]
        dat["groups"][k]["dependency"] = [names[j] for j in dep[i]]
    tmp = []
    for k, v in dat["groups"].items():
        tmp.append((k, v))
    dat["groups"].clear()
    for i in order:
        dat["groups"][tmp[i][0]] = tmp[i][1]
    return "tests"


@actions.bind
def protect_problem(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    if not dat.sql_data.is_public:
        abort(409)
    dat.sql_data.is_public = False
    return "general_info"


@actions.bind
def public_problem(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    if dat.sql_data.is_public:
        abort(409)
    dat.sql_data.is_public = True
    return "general_info"


@actions.bind
def save_languages(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    for k in executing.langs.keys():
        dat["languages"][k] = (form.get("lang_check_" + k, "off") == "on")
    return "languages"


def prepare_gen_group(form: ImmutableMultiDict[str, str], dat: Problem):
    file1 = form["file1"]
    if not any(o["name"] == file1 for o in dat["files"]):
        abort(404)
    file2 = form["file2"]
    if not any(o["name"] == file2 for o in dat["files"]):
        abort(404)
    group = form["group"]
    if group not in dat["groups"]:
        abort(404)
    tp = form["type"]
    if tp not in ("sol", "gen"):
        abort(400)
    return file1, file2, group, tp


@actions.bind
def create_gen_group(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    file1, file2, group, tp = prepare_gen_group(form, dat)
    cnt = tools.to_int(form["mul"])
    cmds = form["cmds"].split("\n")
    out_cmds = []
    for i in range(1, cnt + 1):
        for s in cmds:
            out_cmds.append(s.replace("{index}", str(i)))
    if "gen_groups" not in dat:
        dat["gen_groups"] = []
    dat["gen_groups"].append({"file1": file1, "file2": file2, "group": group, "type": tp, "cmds": out_cmds,
                              "status": "未更新"})
    return "tests"


@actions.bind
def update_gen_group(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    file1, file2, group, tp = prepare_gen_group(form, dat)
    idx = tools.to_int(form["idx"])
    cmds = form["cmds"].split("\n")
    if "gen_groups" not in dat or idx < 0 or idx >= len(dat["gen_groups"]):
        abort(400)
    dat["gen_groups"][idx] = {"file1": file1, "file2": file2, "group": group, "type": tp, "cmds": cmds,
                              "status": "未更新"}
    return "tests"


@actions.bind
def remove_gen_group(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    idx = tools.to_int(form["idx"])
    if "gen_groups" not in dat or idx < 0 or idx >= len(dat["gen_groups"]):
        abort(400)
    dat["gen_groups"].pop(idx)
    return "tests"


@actions.bind
def import_polygon(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    file = request.files["zip_file"]
    filename = f"tmp/{tools.random_string()}.zip"
    file.save(filename)
    add_background_action({"action": "do_import_polygon", "pid": pid, "filename": filename})
    return "import"


@actions.bind
def import_problem(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    zip_file = request.files["zip_file"]
    filename = f"tmp/{tools.random_string()}.zip"
    zip_file.save(filename)
    dirs = ("file", "public_file", "testcases")
    files = ("statement.html", "statement.md")
    with AESZipFile(filename, "r") as zf:
        for file in zf.filelist:
            file: AESZipInfo
            if file.filename in files:
                zf.extract(file, path)
            elif file.filename == "info.json":
                users = dat.dat["users"]
                public_testcase = dat.dat["public_testcase"]
                dat.dat |= json.loads(zf.read(file).decode())
                dat.dat["users"] = users
                dat.dat["public_testcase"] = public_testcase
            else:
                dir_name = os.path.dirname(file.filename)
                if dir_name in dirs:
                    zf.extract(file, path)
    render_statement(pid, dat)
    return "import"


@actions.bind
def export_problem(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem) -> str | Response:
    filename = f"tmp/{tools.random_string()}.zip"
    dirs = ("file", "public_file", "testcases")
    files = ("statement.html", "statement.md")
    with AESZipFile(filename, "w") as zf:
        for name in dirs:
            for f in os.listdir(path + "/" + name):
                zf.write(os.path.join(path, name, f), name + "/" + f)
        for f in files:
            zf.write(os.path.join(path, f), f)
        zf.writestr("info.json", json.dumps(dat.dat, indent=4))
    return sending_file(filename)


def action(form: ImmutableMultiDict[str, str]) -> Response:
    with datas.DelayCommit():
        pid = secure_filename(form["pid"])
        path = f"preparing_problems/{pid}"
        func = actions.get(form["action"])
        important = hasattr(func, "important") and getattr(func, "important")
        with Problem(pid, important) as dat:
            tp = actions.call(form["action"], form, pid, path, dat)
            if type(tp) is str:
                return redirect(f"/problemsetting/{pid}#{tp}")
            else:
                return tp


def sending_file(file: str) -> Response:
    file = os.path.abspath(file)
    if not os.path.exists(file):
        abort(404)
    return send_file(file)


def preview(args: MultiDict[str, str], pdat: datas.Problem) -> Response:
    pid = args["pid"]
    path = f"preparing_problems/{pid}"
    match args["type"]:
        case "statement":
            if not tools.exists(path + "/statement.html"):
                abort(404)
            dat = pdat.new_data
            statement = tools.read(path + "/statement.html")
            lang_exts = json.dumps({k: v.data["source_ext"] for k, v in executing.langs.items()})
            samples = [[tools.read(path, k, o["in"]), tools.read(path, k, o["out"])]
                       for k in ("testcases", "testcases_gen") for o in dat.get(k, []) if o.get("sample", False)]
            ret = render_template("problem.html", dat=dat, statement=statement,
                                  langs=executing.langs.keys(), lang_exts=lang_exts, pid=pid,
                                  preview=True, samples=enumerate(samples))
            return Response(ret)
        case "public_file":
            return sending_file(path + "/public_file/" + secure_filename(args["name"]))
        case "file":
            return sending_file(path + "/file/" + secure_filename(args["name"]))
        case "testcases":
            return sending_file(path + "/testcases/" + secure_filename(args["name"]))
        case "testcases_gen":
            return sending_file(path + "/testcases_gen/" + secure_filename(args["name"]))
    abort(404)


def query_versions(pdat: datas.Problem):
    out = []
    info = pdat.data
    for o in info.get("versions", []):
        out.append({
            "date": str(int(float(o["time"]))),
            "message": o["description"]
        })
    out.reverse()
    for i, o in enumerate(out):
        o["id"] = str(len(out) - i - 1)
    return out
