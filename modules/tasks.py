import os
import traceback
from multiprocessing import Queue, Process

from flask import abort

from modules import executing, constants, tools, locks, datas

submissions_queue = Queue()

last_judged = 0


def create_submission() -> str:
    with tools.File("data/submission_count") as f:
        count = int(f.read())
        count = str(count + 1)
        f.write(count)
    os.mkdir(f"submissions/{count}")
    return count


def run_test(dat: datas.Submission) -> None:
    lang = executing.langs[dat.language]
    env = executing.Environment()
    idx = str(dat.id)
    source = f"submissions/{idx}/" + dat.source
    in_file = os.path.abspath(f"submissions/{idx}/" + dat.data["infile"])
    out_file = os.path.abspath(f"submissions/{idx}/" + dat.data["outfile"])
    result = lang.run(source, env, [(in_file, out_file)])
    dat.result = {"simple_result": result}
    dat.completed = True
    datas.add(dat)


def run_problem(pdat: datas.Problem, dat: datas.Submission) -> None:
    lang = executing.langs[dat.language]
    env = executing.Environment()
    idx = str(dat.id)
    source = f"submissions/{idx}/" + dat.source
    pid = pdat.pid
    problem_path = f"problems/{pid}/"
    problem_info = constants.default_problem_info | pdat.data
    filename, ce_msg = lang.compile(env.send_file(source), env)
    out_info = {"CE": False}
    results = []
    groups = {}
    simple_result = "AC"
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
            int_file = env.send_file(problem_path + "/" + problem_info["interactor"][0], env.judge_executable)
            int_lang = executing.langs[problem_info["interactor"][1]]
            int_exec = int_lang.get_execmd(int_file)
        checker = env.send_file(problem_path + problem_info["checker"][0], env.judge_executable)
        checker_cmd = executing.langs[problem_info["checker"][1]].get_execmd(checker)
        exec_cmd = lang.get_execmd(filename)
        os.mkdir(f"submissions/{idx}/testcases")
        if "groups" in problem_info:
            groups = problem_info["groups"]
        if "default" not in groups:
            groups["default"] = {}
        for o in groups.values():
            o |= {"result": "OK", "time": 0, "mem": 0, "gainscore": top_score if o.get("rule", "min") == "min" else 0}
        testcases = problem_info["testcases"]
        if "testcases_gen" in problem_info:
            testcases.extend([o | {"gen": True} for o in problem_info["testcases_gen"]])
        for i, testcase in enumerate(testcases):
            gp = "default"
            if "group" in testcase and testcase["group"] in groups:
                gp = testcase["group"]
            exist_gp.add(gp)
            if "dependency" in groups[gp]:
                for k in groups[gp]["dependency"]:
                    if groups[k]["result"] != "OK" and groups[k]["result"] != "PARTIAL":
                        groups[gp]["result"] = "SKIP"
            if groups[gp]["result"] != "OK" and groups[gp]["result"] != "PARTIAL":
                results.append({"time": 0, "mem": 0, "result": "SKIP", "info": "Skipped",
                                "has_output": False})
                continue
            tt = "testcases_gen/" if testcase.get("gen", False) else "testcases/"
            in_file = os.path.abspath(problem_path + tt + testcase["in"])
            ans_file = os.path.abspath(problem_path + tt + testcase["out"])
            out_file = os.path.abspath(f"submissions/{idx}/testcases/{i}.out")
            tools.create_truncated(in_file, f"submissions/{idx}/testcases/{i}.in")
            tools.create_truncated(ans_file, f"submissions/{idx}/testcases/{i}.ans")
            env.send_file(in_file)
            if problem_info["is_interact"]:
                env.judge_readable(in_file)
                env.judge_writeable(out_file)
                out = env.runwithinteractshell(exec_cmd, int_exec, env.filepath(in_file), env.filepath(out_file), tl,
                                               ml, lang.base_exec_cmd)
            else:
                out = env.runwithshell(exec_cmd, env.filepath(in_file), env.filepath(out_file), tl, ml,
                                       lang.base_exec_cmd)
            timeusage = 0
            memusage = 0
            has_output = False
            score = 0
            if executing.is_tle(out):
                ret = ["TLE", "執行時間過長"]
            else:
                result = {o[0]: o[1] for o in (s.split("=") for s in out[0].split("\n")) if len(o) == 2}
                print(result)
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
                        full_checker_cmd = checker_cmd + [env.filepath(in_file), env.filepath(out_file),
                                                          env.send_file(ans_file)]
                        env.judge_readable(ans_file, in_file, out_file)
                        checker_out = env.judge_run(full_checker_cmd)
                        env.protected(ans_file, in_file, out_file)
                        env.get_file(out_file)
                        tools.create_truncated(out_file, out_file)
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
                            "has_output": has_output, "score": score})
            if groups[gp]["result"] != ret[0] and ret[0] != "OK":
                groups[gp]["result"] = ret[0]
            if ret[0] != "OK":
                simple_result = "NA"
            if groups[gp].get("rule", "min") == "min":
                groups[gp]["gainscore"] = min(groups[gp]["gainscore"], score)
            else:
                groups[gp]["gainscore"] += score
            groups[gp]["cnt"] = groups[gp].get("cnt", 0) + 1
        for o in groups.values():
            if o.get("cnt", 0):
                if o.get("rule", "min") == "avg":
                    o["gainscore"] /= o.get("cnt", 0)
                total_score += o["gainscore"] * o.get("score", 100) / top_score
    out_info["results"] = results
    keys = ("result", "time", "mem", "gainscore")
    out_info["group_results"] = {k: {key: v[key] for key in keys} for k, v in groups.items() if k in exist_gp}
    out_info["simple_result"] = simple_result
    out_info["total_score"] = total_score
    out_info["protected"] = dat.user.username not in problem_info["users"]
    dat.result = out_info
    dat.completed = True
    datas.add(dat)


def get_queue_position(idx: str) -> int:
    if not idx.isdigit():
        abort(400)
    return max(int(idx) - last_judged.value, 0)


def runner():
    while True:
        idx: int = int(submissions_queue.get())
        dat: datas.Submission = datas.Submission.query.get(idx)
        try:
            last_judged.value = idx
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
            tools.write("".join(traceback.format_exception(e)), "logs", log_uuid + ".log")
            dat.completed = True
            datas.add(dat)


def init():
    Process(target=runner).start()
    datas.Submission.query.count()
