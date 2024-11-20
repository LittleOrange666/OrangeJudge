import math
import multiprocessing
import time
import traceback
from pathlib import Path

from loguru import logger

from . import executing, constants, tools, locks, datas, config, judge
from .constants import log_path
from .judge import SandboxUser

last_judged = locks.Counter()

queue_position = locks.Counter()


def run(lang: executing.Language, file: Path, env: executing.Environment, stdin: Path, stdout: Path,
        dat: datas.Submission) -> str:
    """
    Execute and evaluate a submitted program.

    This function compiles the submitted code, runs it with the provided input,
    and evaluates the output. It handles various execution scenarios including
    compilation errors, runtime errors, time limit exceeded, and successful runs.

    Parameters:
    lang (executing.Language): The programming language of the submission.
    file (Path): Path to the submitted source code file.
    env (executing.Environment): The execution environment.
    stdin (Path): Path to the input file.
    stdout (Path): Path to the output file.
    dat (datas.Submission): The submission data object.

    Returns:
    str: A string indicating the result of the execution. Possible values include:
         "CE" for Compilation Error,
         "TLE" for Time Limit Exceeded,
         "OLE" for Output Limit Exceeded,
         "RE" for Runtime Error (with additional details),
         "OK" for successful execution (with time and memory usage).
    """
    filename = env.send_file(file)
    filename, ce_msg = lang.compile(filename, env)
    if ce_msg:
        dat.ce_msg = ce_msg
        return "CE"
    exec_cmd = lang.get_execmd(filename)
    Path(stdout).touch()
    in_file = env.send_rand_file(stdin)
    out_file = env.send_rand_file(stdout)
    err_file = env.path("stderr.txt")
    SandboxUser.running.readable(in_file)
    SandboxUser.running.writeable(out_file)
    res = env.run(exec_cmd, 10 * 1000, 1000, in_file, out_file, err_file, user=SandboxUser.running,
                  seccomp_rule=lang.seccomp_rule)
    logger.debug(res)
    if res.result == "JE":
        return "JE: " + res.error
    if res.result == "TLE":
        return "TLE: Testing is limited by 10 seconds"
    tools.copy(err_file.full, Path(file).parent / "stderr.txt")
    if res.result == "RE":
        exit_code = str(res.exit_code)
        msg = constants.exit_codes.get(exit_code, exit_code)
        sig_name = str(res.signal)
        if sig_name in constants.signal_names:
            sig_name = f"{sig_name} ({constants.signal_names[sig_name]})"
        return f"RE: {msg}: signal {sig_name}"
    if res.result == "MLE":
        return "MLE: Testing is limited by 1000 MB"
    env.get_file(stdout, out_file)
    time_usage = max(0, res.cpu_time - lang.base_time)
    memusage = max(0, res.memory - lang.base_memory)
    return f"OK: {time_usage}ms, {memusage}B"


def run_test(dat: datas.Submission) -> None:
    lang = executing.langs[dat.language]
    env = executing.Environment()
    idx = str(dat.id)
    logger.info("run test", idx)
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
        env.send_file(pdat.path / "file" / fn, env.executable)
    sent_source = env.send_file(source)
    if problem_info.get("runner_enabled", False):
        judge_runner = env.send_file(p_path / "file" / problem_info.get("runner_source", {}).get(dat.language))
        judge_runner = env.rename(judge_runner, constants.runner_source_file_name + lang.data["source_ext"])
        filename, ce_msg = lang.compile(sent_source, env, judge_runner)
    else:
        filename, ce_msg = lang.compile(sent_source, env)
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
        tl = int(problem_info["timelimit"])
        ml = int(problem_info["memorylimit"])
        int_exec = []
        if problem_info["is_interact"]:
            int_file = env.send_file(p_path / problem_info["interactor"][0], SandboxUser.judge.executable)
            int_lang = executing.langs[problem_info["interactor"][1]]
            int_exec = int_lang.get_execmd(int_file)
        if problem_info.get("codechecker_mode", "disabled") != "disabled":
            cc_file = env.send_file(p_path / problem_info["codechecker"][0], SandboxUser.judge.executable)
            cc_lang = executing.langs[problem_info["codechecker"][1]]
            cc_exec = cc_lang.get_execmd(cc_file)
            res = env.call(cc_exec + [str(sent_source.sandbox), lang.branch])  # here should resolve errors
            env.path("codechecker_result.txt").full.write_text(res.stdout)
            (dat.path / "codechecker_result.txt").write_text(res.stdout)
        checker = env.send_file(p_path / problem_info["checker"][0], SandboxUser.judge.executable)
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
            ret = []
            if just_pretest and not testcase.get("pretest", False):
                ret = ["OK", "Skip by pretest policy"]
                score = top_score
            else:
                in_path = env.send_rand_file(in_file)
                out_path = env.send_rand_file(out_file)
                if problem_info["is_interact"]:
                    SandboxUser.judge.readable(in_path)
                    SandboxUser.judge.writeable(out_path)
                    interr = env.path("interr.txt")
                    all_res = env.interact_run(exec_cmd, int_exec, tl, ml, in_path, out_path,
                                               user=SandboxUser.running,
                                               interact_user=SandboxUser.judge,
                                               seccomp_rule=lang.seccomp_rule, interact_err_file=interr)
                    res = all_res.result
                    if all_res.interact_result.result == "RE":
                        ret = ["WA", interr.full.read_text()]
                else:
                    SandboxUser.running.readable(in_path)
                    SandboxUser.running.writeable(out_path)
                    res = env.run(exec_cmd, tl, ml, in_path, out_path, user=SandboxUser.running
                                  , seccomp_rule=lang.seccomp_rule)
                exit_code = str(res.exit_code)
                if res.result == "JE":
                    ret = ["JE", res.error]
                elif res.result == "TLE":
                    ret = ["TLE", "執行時間過長"]
                elif res.result == "MLE":
                    ret = ["MLE", "記憶體占用過大"]
                elif exit_code == "153":
                    ret = ["OLE", "輸出過大"]
                elif res.result == "RE":
                    if exit_code in constants.exit_codes:
                        ret = ["RE", constants.exit_codes[exit_code]]
                    else:
                        ret = ["RE", "執行期間錯誤"]
                elif len(ret) == 0:  # skip code below if interactor return with non-zero return code
                    timeusage = max(0, res.cpu_time - lang.base_time)
                    memusage = math.ceil(max(0, res.memory - lang.base_memory) / 1024)
                    groups[gp]["time"] = max(groups[gp]["time"], timeusage)
                    groups[gp]["mem"] = max(groups[gp]["mem"], memusage)
                    has_output = True
                    ans_path = env.send_rand_file(ans_file)
                    full_checker_cmd = checker_cmd + [in_path, out_path, ans_path]
                    env.readable(ans_path, in_path, out_path, user=SandboxUser.judge)
                    checker_out = env.call(full_checker_cmd, user=SandboxUser.judge)
                    env.protected(ans_path, in_path, out_path)
                    env.get_file(out_file, out_path)
                    tools.create_truncated(Path(out_file), Path(out_file))
                    if judge.is_tle(checker_out):
                        ret = ["JE", "checker TLE"]
                    else:
                        if checker_out.stderr.startswith("partially correct"):
                            score = checker_out.return_code
                            name = "OK" if score >= top_score else "PARTIAL"
                        else:
                            name = constants.checker_exit_codes.get(checker_out.return_code, "JE")
                            if name == "OK":
                                score = top_score
                            elif name == "POINTS":
                                st = checker_out.stderr.split(" ")
                                if len(st) > 1 and st[1].replace(".", "", 1).isdigit():
                                    score = float(st[1])
                                name = "OK" if score >= top_score else "PARTIAL"
                        score = max(score, 0)
                        ret = [name, checker_out.stderr]
            if ret[0] == "TLE":
                timeusage = tl
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
    logger.info(f"get {idx}")
    try:
        for _ in range(5):
            dat: datas.Submission = datas.Submission.query.get(idx)
            if dat is not None:
                try:
                    dat.running = True
                    datas.add(dat)
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


def queue_receiver():
    while True:
        submissions = datas.Submission.query.filter_by(completed=False, running=False)
        if submissions.count() == 0:
            time.sleep(10)
            continue
        dat = submissions.first()
        runner(dat.id)
        time.sleep(1)


def enqueue(idx: int) -> int:
    logger.info(f"enqueue {idx}")
    return queue_position.inc()


def init():
    for submission in datas.Submission.query.filter_by(completed=False):
        enqueue(submission.id)
    for _ in range(config.judge.workers):
        multiprocessing.Process(target=queue_receiver, daemon=True).start()
