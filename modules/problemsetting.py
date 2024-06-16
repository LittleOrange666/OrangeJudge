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
    if problem["is_interact"]:
        int_cmd = problem.compile_inner(problem["interactor_source"], "interactor", env)
    tl = float(problem["timelimit"]) / 1000
    ml = int(problem["memorylimit"])
    if "gen_msg" in problem:
        i = 1
        tests = []
        seed = problem["gen_msg"]["seed"]
        for k, v in problem["gen_msg"]["counts"].items():
            for j in range(int(v)):
                tests.append((f"{k}_{j + 1}", [str(i), k, seed]))
                i += 1
        exec_cmd = problem.compile_inner(problem["gen_msg"]["generator"], "generator", env)
        sol_cmd = problem.compile_inner(problem["gen_msg"]["solution"], "solution", env)
        sol_lang = problem.lang(problem["gen_msg"]["solution"])
        if os.path.isdir(path + "/testcases_gen/"):
            shutil.rmtree(path + "/testcases_gen/")
        os.makedirs(path + "/testcases_gen/", exist_ok=True)
        for test in tests:
            in_file = os.path.abspath(path + "/testcases_gen/" + test[0] + ".in")
            out_file = os.path.abspath(path + "/testcases_gen/" + test[0] + ".out")
            log(f"generating testcase {test[0]!r}")
            gen_out = env.safe_run(exec_cmd + test[1])
            if gen_out[2]:
                log("generator RE")
                log(gen_out[1])
                end(False)
            tools.write(gen_out[0], in_file)
            env.send_file(in_file)
            if problem["is_interact"]:
                env.judge_readable(in_file)
                env.judge_writeable(out_file)
                out = env.runwithinteractshell(sol_cmd, int_cmd, env.filepath(in_file), env.filepath(out_file), tl, ml,
                                               sol_lang.base_exec_cmd)
            else:
                out = env.runwithshell(sol_cmd, env.filepath(in_file), env.filepath(out_file), tl, ml,
                                       sol_lang.base_exec_cmd)
            result = {o[0]: o[1] for o in (s.split("=") for s in out[0].split("\n")) if len(o) == 2}
            if "1" == result.get("WIFSIGNALED", None) or "0" != result.get("WEXITSTATUS", "0"):
                log("solution RE")
                log(out[1])
                end(False)
            env.get_file(out_file)
        log(f"generate complete")
        gen_list += [{"in": test[0] + ".in", "out": test[0] + ".out", "sample": False, "pretest": False,
                      "group": test[1][1]} for test in tests]
    if "ex_gen_msg" in problem:
        sol = problem["ex_gen_msg"]["solution"]
        cmds = problem["ex_gen_msg"]["cmds"]
        sol_cmd = problem.compile_inner(sol, "solution", env)
        sol_lang = problem.lang(sol)
        gens = list({cmd[0].split()[0] for cmd in cmds})
        gen_exec = {}
        tools.log(problem["files"])
        tools.log(gens)
        for k in gens:
            if not any(file["name"].startswith(k + ".") for file in problem["files"]):
                log(f"unknown generator {k!r}")
        for k in gens:
            gen = next(file["name"] for file in problem["files"] if file["name"].startswith(k + "."))
            gen_exec[k] = problem.compile_inner(gen, f"generator({k})", env)
        for i, test in enumerate(cmds):
            test = test[0].split()
            in_file = os.path.abspath(path + f"/testcases_gen/{i}_exgen.in")
            out_file = os.path.abspath(path + f"/testcases_gen/{i}_exgen.out")
            log(f"generating ex testcase {i}")
            gen_out = env.safe_run(gen_exec[test[0]] + test[1:])
            if gen_out[2]:
                log("generator RE")
                log(gen_out[1])
                end(False)
            tools.write(gen_out[0], in_file)
            env.send_file(in_file)
            if problem["is_interact"]:
                env.judge_readable(in_file)
                env.judge_writeable(out_file)
                out = env.runwithinteractshell(sol_cmd, int_cmd, env.filepath(in_file), env.filepath(out_file), tl, ml,
                                               sol_lang.base_exec_cmd)
            else:
                out = env.runwithshell(sol_cmd, env.filepath(in_file), env.filepath(out_file), tl, ml,
                                       sol_lang.base_exec_cmd)
            result = {o[0]: o[1] for o in (s.split("=") for s in out[0].split("\n")) if len(o) == 2}
            if "1" == result.get("WIFSIGNALED", None) or "0" != result.get("WEXITSTATUS", "0"):
                log("solution RE")
                log(out[1])
                end(False)
            env.get_file(out_file)
        gen_list += [
            {"in": f"{i}_exgen.in", "out": f"{i}_exgen.out", "sample": False, "pretest": False, "group": test[1]}
            for i, test in enumerate(cmds)]
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
    dat["files"].append({"name": fn, "type": constants.polygon_type.get(checker.get("type"), "C++17")})
    interactor = assets.find("interactor")
    if interactor:
        source = interactor.find("source")
        fn = "interactor_" + os.path.basename(source.get("path"))
        tools.write_binary(zip_file.read(files[source.get("path")]), path, "file", fn)
        dat["interactor_source"] = fn
        dat["files"].append({"name": fn, "type": constants.polygon_type.get(source.get("type"), "C++17")})
        dat["is_interact"] = True
    main_sol = None
    for solution in assets.find("solutions").iter("solution"):
        source = solution.find("source")
        fn = "solution_" + os.path.basename(source.get("path"))
        tools.write_binary(zip_file.read(files[source.get("path")]), path, "file", fn)
        dat["files"].append({"name": fn, "type": constants.polygon_type.get(source.get("type"), "C++17")})
        if solution.get("tag") == "main":
            main_sol = fn
        tools.log(source.get("path"), solution.get("tag"))
    if main_sol:
        dat["ex_gen_msg"] = {"solution": main_sol, "cmds": gen_cmds}
    for executable in root.iter("executable"):
        source = executable.find("source")
        fn = os.path.basename(source.get("path"))
        tools.write_binary(zip_file.read(files[source.get("path")]), path, "file", fn)
        dat["files"].append({"name": fn, "type": constants.polygon_type.get(source.get("type"), "C++17")})
    fake_form = {k: "" for k in constants.polygon_statment}
    fake_form["samples"] = "[]"
    for k, v in constants.polygon_statment.items():
        if v in files:
            fake_form[k] = zip_file.read(files[v]).decode()
    fake_form["statement_type"] = "latex"
    save_statement(fake_form, pid, path, dat)
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
def save_general_info(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem):
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
def create_version(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem):
    description = form["description"]
    add_background_action({"action": "creating_version", "pid": pid, "description": description})
    return "versions"


@actions.bind
def save_statement(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem):
    dat["manual_samples"] = tools.form_json(form["samples"])
    obj = dat["statement"]
    obj["main"] = form["statement_main"]
    obj["input"] = form["statement_input"]
    obj["output"] = form["statement_output"]
    obj["interaction"] = form["statement_interaction"]
    obj["scoring"] = form["statement_scoring"]
    obj["type"] = form.get("statement_type", "md")
    if obj["type"] == "latex":
        obj["main"], obj["input"], obj["output"], obj["interaction"], obj["scoring"] = \
            createhtml.run_latex(pid, [obj["main"], obj["input"], obj["output"], obj["interaction"], obj["scoring"]])
    full = "# 題目敘述\n" + obj["main"] + "\n## 輸入說明\n" + obj["input"] + "\n## 輸出說明\n" \
           + obj["output"]
    if obj["interaction"]:
        full += "\n## 互動說明\n" + form["statement_interaction"]
    if obj["scoring"]:
        full += "\n## 配分\n" + form["statement_scoring"]
    tools.write(full, f"preparing_problems/{pid}/statement.md")
    createhtml.parse.dirname = pid
    tools.write(createhtml.run_markdown(full), f"preparing_problems/{pid}/statement.html")
    return "statement"


@make_important
@actions.bind
def upload_zip(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem):
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
        with open(path + "/testcases/" + f0, "wb") as f:
            f.write(zip_file.read(o[0]))
        with open(path + "/testcases/" + f1, "wb") as f:
            f.write(zip_file.read(o[1]))
        if (f0, f1) not in fps:
            dat["testcases"].append({"in": f0, "out": f1, "sample": "sample" in f0, "pretest": "pretest" in f0})
    os.remove(filename)
    return "tests"


@actions.bind
def upload_public_file(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem):
    get_files = request.files.getlist("files")
    for file in get_files:
        fn = secure_filename(file.filename)
        if fn == "":
            abort(400)
        if tools.exists(path, "public_file", fn):
            abort(409)
    for file in get_files:
        fn = secure_filename(file.filename)
        file.save(path + "/public_file/" + fn)
    return "files"


@actions.bind
def remove_public_file(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem):
    filename = form["filename"]
    filepath = path + "/public_file/" + secure_filename(filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    else:
        abort(404)
    return "files"


@actions.bind
def upload_file(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem):
    get_files = request.files.getlist("files")
    for file in get_files:
        if secure_filename(file.filename) == "":
            abort(400)
        if tools.exists(path, "file/", secure_filename(file.filename)):
            abort(409)
        file.save(path + "/file/" + secure_filename(file.filename))
        dat["files"].append({"name": secure_filename(file.filename), "type": "C++17"})
    return "files"


@actions.bind
def create_file(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem):
    filename = secure_filename(form["filename"])
    if tools.exists(path, "file", filename):
        abort(409)
    tools.create(path, "file", filename)
    dat["files"].append({"name": filename, "type": "C++17"})
    return "files"


@actions.bind
def remove_file(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem):
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
def save_file_content(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem):
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
def choose_checker(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem):
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
def choose_interactor(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem):
    tp = "my"
    name = secure_filename(form[tp + "_interactor"])
    use = form.get("enable_interactor", "off") == "on"
    if not any(o["name"] == name for o in dat["files"]):
        abort(404)
    dat["interactor_source"] = name
    dat["is_interact"] = use
    return "judge"


@actions.bind
def save_testcase(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem):
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
def save_testcase_gen(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem):
    try:
        modify = json.loads(form["modify"])
    except json.decoder.JSONDecodeError:
        abort(400)
    testcases = dat["testcases_gen"]
    if type(modify) is not list or len(modify) != len(testcases):
        abort(400)
    s = set()
    new_testcases = []
    for o in modify:
        if type(o[1]) is not bool or type(o[0]) is not int or not (len(testcases) > o[0] >= 0):
            abort(400)
        if o[0] in s:
            abort(400)
        s.add(o[0])
        obj = testcases[o[0]]
        obj["sample"] = o[1]
        new_testcases.append(obj)
    dat["testcases_gen"] = new_testcases
    return "tests"


@actions.bind
def set_generator(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem):
    generator = form["generator"]
    solution = form["solution"]
    if not any(o["name"] == generator for o in dat["files"]):
        abort(404)
    if not any(o["name"] == solution for o in dat["files"]):
        abort(404)
    seed = form["seed"]
    cnts = {}
    for k in dat["groups"].keys():
        cnts[k] = form["count_" + k]
        if not cnts[k].isdigit():
            abort(400)
    dat["gen_msg"] = {"generator": generator, "solution": solution, "seed": seed, "counts": cnts}
    return "tests"


@actions.bind
def do_generate(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem):
    add_background_action({"action": "generate_testcase", "pid": pid})
    return "tests"


@actions.bind
def create_group(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem):
    name = secure_filename(form["name"].strip())
    if name in dat["groups"]:
        abort(409)
    dat["groups"][name] = {"score": 100, "rule": "min", "dependency": []}
    return "tests"


@actions.bind
def remove_group(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem):
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
def save_groups(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem):
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
def protect_problem(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem):
    if not dat.get("public", False):
        abort(409)
    dat["public"] = False
    dat.sql_data.is_public = False
    # with tools.Json("data/public_problems.json") as pubs:
    #    if pid in pubs:
    #        del pubs[pid]
    return "general_info"


@actions.bind
def public_problem(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem):
    if dat.get("public", False):
        abort(409)
    dat["public"] = True
    dat.sql_data.is_public = True
    # with tools.Json("data/public_problems.json") as pubs:
    #    pubs[pid] = dat["name"]
    return "general_info"


@actions.bind
def import_polygon(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem):
    file = request.files["zip_file"]
    filename = f"tmp/{tools.random_string()}.zip"
    file.save(filename)
    add_background_action({"action": "do_import_polygon", "pid": pid, "filename": filename})
    return "general_info"


@actions.bind
def save_languages(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem):
    for k in executing.langs.keys():
        dat["languages"][k] = (form.get("lang_check_" + k, "off") == "on")
    return "languages"


@actions.bind
def create_gen_group(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem):
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
    cnt = tools.to_int(form["mul"])
    cmds = form["cmds"].split("\n")
    out_cmds = []
    for i in range(1, cnt+1):
        for s in cmds:
            out_cmds.append(s.replace("{index}", str(i)))
    if "gen_groups" not in dat:
        dat["gen_groups"] = []
    dat["gen_groups"].append({"file1": file1, "file2": file2, "group": group, "type": tp, "cmds": out_cmds,
                              "status": "未更新"})


@actions.bind
def update_gen_group(form: ImmutableMultiDict[str, str], pid: str, path: str, dat: Problem):
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
    idx = tools.to_int(form["idx"])
    cmds = form["cmds"].split("\n")
    if "gen_groups" not in dat or idx < 0 or idx >= len(dat["gen_groups"]):
        abort(400)
    dat["gen_groups"][idx] = {"file1": file1, "file2": file2, "group": group, "type": tp, "cmds": cmds,
                              "status": "未更新"}
    return "tests"


def action(form: ImmutableMultiDict[str, str]) -> Response:
    pid = secure_filename(form["pid"])
    path = f"preparing_problems/{pid}"
    func = actions.get(form["action"])
    important = hasattr(func, "important") and getattr(func, "important")
    with Problem(pid, important) as dat:
        tp = actions.call(form["action"], form, pid, path, dat)
        return redirect(f"/problemsetting/{pid}#{tp}")


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
