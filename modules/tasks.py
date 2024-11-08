import atexit
import threading
import time
import traceback
from multiprocessing import Pool, Queue
from pathlib import Path

from .constants import log_path
from . import executing, constants, tools, locks, datas, config

last_judged = locks.Counter()

submission_queue = Queue()

queue_position = locks.Counter()


def run(lang: executing.Language, file: Path, env: executing.Environment, stdin: Path, stdout: Path,
        dat: datas.Submission) -> str:
    filename = env.send_file(file)
    filename, ce_msg = lang.compile(filename, env)
    if ce_msg:
        dat.ce_msg = ce_msg
        return "CE"
    exec_cmd = lang.get_execmd(filename)
    Path(stdout).touch()
    outf = env.send_file(stdout)
    out = env.runwithshell(exec_cmd, env.send_file(stdin), outf, 10, 1000, lang.base_exec_cmd)
    if executing.is_tle(out):
        return "TLE: Testing is limited by 10 seconds"
    result = {o[0]: o[1] for o in (s.split("=") for s in out[0].split("\n")) if len(o) == 2}
    tools.log(out)
    tools.write(out[1], Path(file).parent / "stderr.txt")
    if "1" == result.get("WIFSIGNALED", None):
        return "RE: " + "您的程式無法正常執行"
    exit_code = result.get("WEXITSTATUS", "0")
    if "153" == exit_code:
        return "OLE"
    if "0" != exit_code:
        if exit_code in constants.exit_codes:
            return "RE: " + constants.exit_codes[exit_code]
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


def run_test(dat: datas.Submission) -> None:
    lang = executing.langs[dat.language]
    env = executing.Environment()
    idx = str(dat.id)
    print("run test", idx)
    source = dat.path / dat.source
    in_file = dat.path / dat.data["infile"]
    out_file = dat.path / dat.data["outfile"]
    result = run(lang, source, env, in_file, out_file, dat)
    dat.result = {}
    dat.simple_result = result
    dat.completed = True
    datas.add(dat)


def run_problem(pdat: datas.Problem, dat: datas.Submission) -> None:
    lang = executing.langs[dat.language]
    env = executing.Environment()
    source = dat.path / dat.source
    p_path = pdat.path
    problem_info = constants.default_problem_info | pdat.data
    for fn in problem_info.get("library", []):
        env.send_file(pdat.path / "file" / fn)
    if problem_info.get("runner_enabled", False):
        judge_runner = env.send_file(p_path / "file" / problem_info.get("runner_source", {}).get(dat.language))
        judge_runner = env.rename(judge_runner, constants.runner_source_file_name + lang.data["source_ext"])
        filename, ce_msg = lang.compile(env.send_file(source), env, judge_runner)
    else:
        filename, ce_msg = lang.compile(env.send_file(source), env)
    out_info = {"CE": False}
    results = []
    groups = {}
    just_pretest: bool = dat.just_pretest
    simple_result = "pretest passed" if just_pretest else "AC"
    top_score = problem_info.get("top_score", 100)
    total_score = 0
    exist_gp = set()
    if ce_msg:
        dat.ce_msg = ce_msg
        out_info["CE"] = True
        simple_result = "CE"
    else:
        tl = float(problem_info["timelimit"]) / 1000
        ml = int(problem_info["memorylimit"])
        int_exec = []
        if problem_info["is_interact"]:
            int_file = env.send_file(p_path / problem_info["interactor"][0], env.judge_executable)
            int_lang = executing.langs[problem_info["interactor"][1]]
            int_exec = int_lang.get_execmd(int_file)
        checker = env.send_file(p_path / problem_info["checker"][0], env.judge_executable)
        checker_cmd = executing.langs[problem_info["checker"][1]].get_execmd(checker)
        exec_cmd = lang.get_execmd(filename)
        testcase_path = dat.path / "testcases"
        testcase_path.mkdir(parents=True, exist_ok=True)
        if "groups" in problem_info:
            groups = problem_info["groups"]
        if "default" not in groups:
            groups["default"] = {}
        for o in groups.values():
            o |= {"result": "OK", "time": 0, "mem": 0, "gainscore": top_score if o.get("rule", "min") == "min" else 0}
        testcases: list = problem_info["testcases"]
        if "testcases_gen" in problem_info:
            testcases.extend([o | {"gen": True} for o in problem_info["testcases_gen"]])
        group_testcases = {k: [] for k in groups}
        for obj in testcases:
            group_testcases[obj.get("group", "default")].append(obj)
        testcases.clear()
        for k, v in group_testcases.items():
            testcases.extend(v)
        for i, testcase in enumerate(testcases):
            gp = testcase.get("group", "default")
            is_sample = testcase.get("sample", False)
            exist_gp.add(gp)
            if "dependency" in groups[gp]:
                for k in groups[gp]["dependency"]:
                    if groups[k]["result"] != "OK" and groups[k]["result"] != "PARTIAL":
                        groups[gp]["result"] = "SKIP"
            if groups[gp]["result"] != "OK" and groups[gp]["result"] != "PARTIAL":
                results.append({"time": 0, "mem": 0, "result": "SKIP", "info": "Skipped",
                                "has_output": False})
                continue
            timeusage = 0
            memusage = 0
            has_output = False
            score = 0
            tt = "testcases_gen" if testcase.get("gen", False) else "testcases"
            in_file = p_path / tt / testcase["in"]
            ans_file = p_path / tt / testcase["out"]
            out_file = testcase_path / f"{i}.out"
            tools.create_truncated(Path(in_file), testcase_path / f"{i}.in")
            tools.create_truncated(Path(ans_file), testcase_path / f"{i}.ans")
            if just_pretest and not testcase.get("pretest", False):
                ret = ["OK", "Skip by pretest policy"]
                score = top_score
            else:
                in_path = env.send_file(in_file)
                out_path = env.path(out_file.name)
                if problem_info["is_interact"]:
                    env.judge_readable(in_path)
                    env.judge_writeable(out_path)
                    out = env.runwithinteractshell(exec_cmd, int_exec, in_path, out_path, tl, ml, lang.base_exec_cmd)
                else:
                    out = env.runwithshell(exec_cmd, in_path, out_path, tl, ml, lang.base_exec_cmd)
                if executing.is_tle(out):
                    ret = ["TLE", "執行時間過長"]
                else:
                    result = {o[0]: o[1] for o in (s.split("=") for s in out[0].split("\n")) if len(o) == 2}
                    tools.log(result)
                    exit_code = result.get("WEXITSTATUS", "0")
                    if "1" == result.get("WIFSIGNALED", None):
                        ret = ["RE", "您的程式無法正常執行"]
                    elif "0" != exit_code:
                        if "153" == exit_code:
                            ret = ["OLE", "輸出過多"]
                        elif exit_code in constants.exit_codes:
                            ret = ["RE", constants.exit_codes[exit_code]]
                        else:
                            ret = ["RE", out[1]]
                    else:
                        if "time" in result and float(result["time"]) >= 0:
                            timeusage = int((float(result["time"]) + float(result["basetime"])) * 1000)
                        if "mem" in result and float(result["mem"]) >= 0:
                            memusage = (int(result["mem"]) - int(result["basemem"])) * int(result["pagesize"]) // 1000
                        groups[gp]["time"] = max(groups[gp]["time"], timeusage)
                        groups[gp]["mem"] = max(groups[gp]["mem"], memusage)
                        if timeusage > tl * 950:
                            ret = ["TLE", "執行時間過長"]
                        elif memusage > ml * 1024:
                            ret = ["MLE", "記憶體超出限制"]
                        else:
                            has_output = True
                            ans_path = env.send_file(ans_file)
                            full_checker_cmd = checker_cmd + [in_path, out_path, ans_path]
                            env.judge_readable(ans_path, in_path, out_path)
                            checker_out = env.judge_run(full_checker_cmd)
                            env.protected(ans_path, in_path, out_path)
                            env.get_file(out_file)
                            tools.create_truncated(Path(out_file), Path(out_file))
                            if checker_out[1].startswith("partially correct"):
                                score = checker_out[2]
                                name = "OK" if score >= top_score else "PARTIAL"
                            else:
                                name = constants.judge_exit_codes.get(checker_out[2], "JE")
                                if name == "OK":
                                    score = top_score
                                elif name == "POINTS":
                                    st = checker_out[1].split(" ")
                                    if len(st) > 1 and st[1].replace(".", "", 1).isdigit():
                                        score = float(st[1])
                                    name = "OK" if score >= top_score else "PARTIAL"
                            score = max(score, 0)
                            ret = [name, checker_out[1]]
            if ret[0] == "TLE":
                timeusage = tl * 1000
            results.append({"time": timeusage, "mem": memusage, "result": ret[0], "info": ret[1],
                            "has_output": has_output, "score": score, "sample": is_sample})
            if ret[0] != "OK":
                simple_result = "NA"
            if groups[gp]["result"] != ret[0] and ret[0] != "OK":
                if groups[gp].get("rule", "min") == "min":
                    groups[gp]["result"] = ret[0]
                else:
                    groups[gp]["result"] = "PARTIAL"
            if groups[gp].get("rule", "min") == "min":
                groups[gp]["gainscore"] = min(groups[gp]["gainscore"], score)
            else:
                groups[gp]["gainscore"] += score
            groups[gp]["cnt"] = groups[gp].get("cnt", 0) + 1
        for o in groups.values():
            if o.get("cnt", 0):
                if o.get("rule", "min") == "avg":
                    o["gainscore"] /= o.get("cnt", 0)
                o["gainscore"] = o["gainscore"] * o.get("score", 100) / top_score
                total_score += o["gainscore"]
            elif o.get("rule", "min") == "avg":
                o["gainscore"] = o.get("score", 100)
    out_info["results"] = results
    keys = ("result", "time", "mem", "gainscore")
    out_info["group_results"] = {k: {key: v[key] for key in keys} for k, v in groups.items() if k in exist_gp}
    if simple_result == "NA":
        simple_result += f" {total_score}%"
    out_info["total_score"] = total_score
    out_info["protected"] = ((not problem_info.get('public_testcase', False) or bool(dat.period_id))
                             and dat.user.username not in problem_info["users"])
    dat.result = out_info
    dat.simple_result = simple_result
    dat.completed = True
    datas.add(dat)


def get_queue_position(dat: datas.Submission) -> int:
    return max((dat.queue_position or 0) - queue_position.value, 0)


def runner(idx: int):
    print("get", idx)
    try:
        for _ in range(5):
            dat: datas.Submission = datas.Submission.query.get(idx)
            if dat is not None:
                try:
                    last_judged.inc()
                    pdat: datas.Problem = dat.problem
                    if pdat.pid == "test":
                        run_test(dat)
                    else:
                        run_problem(pdat, dat)
                except Exception as e:
                    traceback.print_exception(e)
                    dat.data["JE"] = True
                    log_uuid = tools.random_string()
                    dat.data["log_uuid"] = log_uuid
                    tools.write("".join(traceback.format_exception(e)), log_path / (log_uuid + ".log"))
                    dat.completed = True
                    datas.add(dat)
                return
            time.sleep(1)
    except Exception as e:
        traceback.print_exception(e)


def enqueue(idx: int) -> int:
    submission_queue.put(idx)
    return queue_position.inc()


def init():
    judger_pool = Pool(config.judge.workers.value)

    def resolve_pool():
        judger_pool.close()
        judger_pool.terminate()

    atexit.register(resolve_pool)

    def queue_receiver():
        while True:
            idx = submission_queue.get()
            judger_pool.apply_async(runner, (idx,))
    threading.Thread(target=queue_receiver, daemon=True).start()
    for submission in datas.Submission.query.filter_by(completed=False):
        enqueue(submission.id)
