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

import math
import multiprocessing
import time
import traceback
from dataclasses import replace
from pathlib import Path

from loguru import logger

from . import executing, constants, tools, locks, datas, config, judge, objs
from .constants import log_path
from .judge import SandboxUser
from .objs import TaskResult

last_judged = locks.Counter()

queue_position = locks.Counter()

check_lock = multiprocessing.Lock()


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
                  seccomp_rule=lang.seccomp_rule, save_seccomp_info=True)
    logger.debug(res)
    if res.result == "JE":
        return "JE: " + res.error
    if res.result == "TLE":
        return "TLE: The custom test execution time exceeded the 10 second limit"
    tools.copy(err_file.full, Path(file).parent / "stderr.txt")
    if res.result == "RE":
        exit_code = str(res.exit_code)
        msg = constants.exit_codes.get(exit_code, exit_code)
        if res.signal == 31:
            return "RF: Violation of seccomp rules: " + res.seccomp_info
        sig_name = str(res.signal)
        if sig_name in constants.signal_names:
            sig_name = f"{sig_name} ({constants.signal_names[sig_name]})"
        return f"RE: {msg}: signal {sig_name}"
    if res.result == "MLE":
        return "MLE: The custom test execution memory exceeded the 1GB limit"
    env.get_file(stdout, out_file)
    time_usage = max(0.0, res.cpu_time - lang.base_time)
    memusage = max(0.0, res.memory - lang.base_memory)
    return f"OK: {time_usage}ms, {memusage}B"


def run_test(dat_id: int) -> None:
    with datas.SessionContext():
        dat = datas.get_by_id(datas.Submission, dat_id)
        lang = executing.langs[dat.language]
        env = executing.Environment()
        idx = str(dat.id)
        logger.info("run test", idx)
        source = dat.path / dat.source
        info = dat.datas
        in_file = dat.path / info.infile
        out_file = dat.path / info.outfile
        result = run(lang, source, env, in_file, out_file, dat)
        dat.results = objs.SubmissionResult()
        dat.simple_result = result
        dat.completed = True
        datas.add(dat)


def run_problem(pid: str, dat_id: int) -> None:
    with datas.SessionContext():
        dat = datas.get_by_id(datas.Submission, dat_id)
        pdat = datas.first(datas.Problem, pid=pid)
        lang = executing.langs[dat.language]
        env = executing.Environment()
        dat_path = dat.path
        source = dat_path / dat.source
        just_pretest: bool = dat.just_pretest
        p_path = pdat.path
        problem_info = pdat.datas
        protected = ((not problem_info.public_testcase or bool(dat.period_id))
                              and dat.user.username not in problem_info.users)
        language = dat.language
    for fn in problem_info.library:
        env.send_file(pdat.path / "file" / fn, env.executable)
    sent_source = env.send_file(source)
    if problem_info.runner_enabled:
        judge_runner = env.send_file(p_path / "file" / problem_info.runner_source.get(language))
        judge_runner = env.rename(judge_runner, constants.runner_source_file_name + lang.source_ext)
        filename, ce_msg = lang.compile(sent_source, env, judge_runner)
    else:
        filename, ce_msg = lang.compile(sent_source, env)
    out_info = objs.SubmissionResult()
    results: list[objs.TestcaseResult] = []
    simple_result = "pretest passed" if just_pretest else "AC"
    top_score = problem_info.top_score
    total_score = 0
    groups: dict[str, objs.RunningTestcaseGroup] = {}
    appeared_result = set()
    codechecker_msg = ""
    out_info.protected = protected
    if ce_msg:
        with datas.SessionContext():
            dat = datas.get_by_id(datas.Submission, dat_id)
            dat.ce_msg = ce_msg
            out_info.CE = True
            dat.results = out_info
            dat.simple_result = "CE"
            dat.completed = True
            datas.add(dat)
            return
    tl = int(problem_info.timelimit) * problem_info.language_multipliers.get(language, 1)
    ml = int(problem_info.memorylimit)
    int_exec = []
    if problem_info.is_interact:
        int_file = env.send_file(p_path / problem_info.interactor.name, SandboxUser.judge.executable)
        int_lang = executing.langs[problem_info.interactor.lang]
        int_exec = int_lang.get_execmd(int_file)
    codechecker_score = top_score
    if problem_info.codechecker_mode != objs.CodecheckerMode.disabled:
        cc_file = env.send_file(p_path / problem_info.codechecker.name, SandboxUser.judge.executable)
        cc_lang = executing.langs[problem_info.codechecker.lang]
        cc_exec = cc_lang.get_execmd(cc_file)
        res = env.call(cc_exec + [str(sent_source.sandbox), lang.branch])  # here should resolve errors
        env.path("codechecker_result.txt").full.write_text(res.stdout)
        (dat_path / "codechecker_result.txt").write_text(res.stdout)
        codechecker_msg = res.stderr
        if res.stderr.startswith("partially correct"):
            codechecker_score = res.return_code
        else:
            name = constants.checker_exit_codes.get(res.return_code, TaskResult.JE)
            if name is TaskResult.OK:
                codechecker_score = top_score
            elif name is TaskResult.POINTS:
                st = res.stderr.split(" ")
                if len(st) > 1 and st[1].replace(".", "", 1).isdigit():
                    codechecker_score = float(st[1])
    out_info.codechecker_msg = codechecker_msg
    checker = env.send_file(p_path / problem_info.checker.name, SandboxUser.judge.executable)
    checker_cmd = executing.langs[problem_info.checker.lang].get_execmd(checker)
    exec_cmd = lang.get_execmd(filename)
    testcase_path = dat_path / "testcases"
    testcase_path.mkdir(parents=True, exist_ok=True)
    groups_ = problem_info.groups
    if "default" not in groups_:
        groups_["default"] = objs.TestcaseGroup()
    for k, v in groups_.items():
        groups[k] = objs.RunningTestcaseGroup(
            score=v.score, rule=v.rule, dependency=v.dependency,
            gained_score=top_score if v.rule is objs.TestcaseRule.min else 0
        )
    testcases = problem_info.testcases
    testcases.extend([replace(o, gen=True) for o in problem_info.testcases_gen])
    group_testcases = {k: [] for k in groups}
    for obj in testcases:
        group_testcases[obj.group].append(obj)
    testcases.clear()
    for k, v in group_testcases.items():
        testcases.extend(v)
    results = [objs.TestcaseResult(completed=False, result=TaskResult.PENDING, info="Waiting for judge")
               for _ in range(len(testcases))]

    def save_result(completed: bool):
        out_info.results = results
        out_info.group_results = {k: v.to_result() for k, v in groups.items()}
        out_info.total_score = total_score
        with datas.SessionContext():
            dat = datas.get_by_id(datas.Submission, dat_id)
            dat.results = out_info
            simple_result_ = simple_result
            if simple_result_ == "NA":
                simple_result_ = "/".join(sorted(appeared_result))
                if completed:
                    simple_result_ += f" {total_score}%"
            dat.simple_result = simple_result_
            dat.completed = completed
            datas.add(dat)

    unsaved_count = 0
    save_period = config.judge.save_period
    for testcase in testcases:
        gp = testcase.group
        groups[gp].target_cnt += 1
    for i, testcase in enumerate(testcases):
        gp = testcase.group
        is_sample = testcase.sample
        for k in groups[gp].dependency:
            if groups[k].is_zero():
                groups[gp].result = TaskResult.SKIP
        if groups[gp].is_zero() and groups[gp].rule is objs.TestcaseRule.min:
            results[i] = objs.TestcaseResult(result=TaskResult.SKIP, info="Skipped")
            unsaved_count += 1
            continue
        if unsaved_count >= save_period:
            save_result(False)
            unsaved_count = 0
        time_usage = 0
        memusage = 0
        has_output = False
        score = 0
        tt = "testcases_gen" if testcase.gen else "testcases"
        in_file = p_path / tt / testcase.in_file
        ans_file = p_path / tt / testcase.out_file
        out_file = testcase_path / f"{i}.out"
        tools.create_truncated(Path(in_file), testcase_path / f"{i}.in")
        tools.create_truncated(Path(ans_file), testcase_path / f"{i}.ans")
        ret: tuple[TaskResult, str] = (TaskResult.OK, "")
        if just_pretest and not testcase.pretest:
            ret = (TaskResult.OK, "因為只執行預測測試，所以跳過")
            score = top_score
        else:
            in_path = env.send_rand_file(in_file)
            out_path = env.send_rand_file(out_file)
            if problem_info.is_interact:
                SandboxUser.judge.readable(in_path)
                SandboxUser.judge.writeable(out_path)
                interr = env.path("interr.txt")
                all_res = env.interact_run(exec_cmd, int_exec, tl, ml, in_path, out_path,
                                           user=SandboxUser.running,
                                           interact_user=SandboxUser.judge,
                                           seccomp_rule=lang.seccomp_rule, interact_err_file=interr)
                res = all_res.result
                if all_res.interact_result.exit_code != 0:
                    ret = (TaskResult.WA, interr.full.read_text())
            else:
                SandboxUser.running.readable(in_path)
                SandboxUser.running.writeable(out_path)
                res = env.run(exec_cmd, tl, ml, in_path, out_path, user=SandboxUser.running,
                              seccomp_rule=lang.seccomp_rule)
            exit_code = str(res.exit_code)
            if res.result == "JE":
                ret = (TaskResult.JE, res.error)
            elif res.result == "TLE":
                ret = (TaskResult.TLE, "Execution time is too long")
            elif res.result == "MLE":
                ret = (TaskResult.MLE, "Memory usage is too large")
            elif exit_code == "153":
                ret = (TaskResult.OLE, "Output too large")
            elif res.result == "RE":
                if res.signal == 31:
                    ret = (TaskResult.RF, "Violation of seccomp rules")
                elif exit_code in constants.exit_codes:
                    ret = (TaskResult.RE, constants.exit_codes[exit_code])
                else:
                    ret = (TaskResult.RE, "Runtime Error")
            elif ret[0] is TaskResult.OK:  # skip code below if interactor return with non-zero return code
                time_usage = max(0, math.ceil(res.cpu_time - lang.base_time))
                memusage = math.ceil(max(0.0, res.memory - lang.base_memory) / 1024)
                groups[gp].time = max(groups[gp].time, time_usage)
                groups[gp].mem = max(groups[gp].mem, memusage)
                has_output = True
                ans_path = env.send_rand_file(ans_file)
                full_checker_cmd = checker_cmd + [in_path, out_path, ans_path]
                env.readable(ans_path, in_path, out_path, user=SandboxUser.judge)
                checker_out = env.call(full_checker_cmd, user=SandboxUser.judge)
                env.protected(ans_path, in_path, out_path)
                env.get_file(out_file, out_path)
                tools.create_truncated(Path(out_file), Path(out_file))
                if judge.is_tle(checker_out):
                    ret = (TaskResult.FAIL, "Checker 執行時間過長")
                else:
                    if checker_out.stderr.startswith("partially correct"):
                        score = checker_out.return_code
                        name = "OK" if score >= top_score else "PARTIAL"
                    else:
                        name = constants.checker_exit_codes.get(checker_out.return_code, TaskResult.FAIL)
                        if name is TaskResult.OK:
                            score = top_score
                        elif name is TaskResult.POINTS:
                            st = checker_out.stderr.split(" ")
                            if len(st) > 1 and st[1].replace(".", "", 1).isdigit():
                                score = float(st[1])
                            name = TaskResult.OK if score >= top_score else TaskResult.PARTIAL
                    score = max(score, 0)
                    ret = (name, checker_out.stderr)
        if codechecker_score < top_score:
            score = score * codechecker_score / top_score
        if ret[0] == TaskResult.TLE:
            time_usage = tl
        result_tp = TaskResult.PASS if just_pretest and not testcase.pretest else ret[0]
        results[i] = objs.TestcaseResult(time=time_usage, mem=memusage, result=result_tp, info=ret[1],
                                         has_output=has_output, score=score, sample=is_sample)
        if ret[0] is not TaskResult.OK:
            appeared_result.add(ret[0].name)
            simple_result = "NA"
        if groups[gp].result is not ret[0] and groups[gp].result is TaskResult.OK:
            if groups[gp].rule is objs.TestcaseRule.min:
                groups[gp].result = ret[0]
            else:
                groups[gp].result = TaskResult.PARTIAL
        if groups[gp].rule is objs.TestcaseRule.min:
            groups[gp].gained_score = min(groups[gp].gained_score, score)
        else:
            groups[gp].gained_score += score
        groups[gp].cnt += 1
        unsaved_count += 1
    for o in groups.values():
        if o.cnt:
            if o.rule is objs.TestcaseRule.avg:
                o.gained_score /= o.cnt
            o.gained_score = o.gained_score * o.score / top_score
            total_score += o.gained_score
        elif o.rule is objs.TestcaseRule.avg:
            o.gained_score = o.score
    save_result(True)


def get_queue_position(dat: datas.Submission) -> int:
    return max((dat.queue_position or 0) - queue_position.value, 0)


def runner(dat_id: int, pid: str):
    logger.info(f"get {dat_id} with problem {pid!r}")
    try:
        if pid == "test":
            run_test(dat_id)
        else:
            run_problem(pid, dat_id)
    except Exception as e:
        traceback.print_exception(e)
        with datas.SessionContext():
            dat = datas.get_by_id(datas.Submission, dat_id)
            info = dat.datas
            info.JE = True
            log_uuid = tools.random_string()
            info.log_uuid = log_uuid
            dat.datas = info
            tools.write("".join(traceback.format_exception(e)), log_path / (log_uuid + ".log"))
            dat.completed = True
            dat.running = False
            datas.add(dat)


def queue_receiver():
    while True:
        try:
            dat_id = None
            pid = None
            with check_lock:
                with datas.SessionContext():
                    dat = datas.first(datas.Submission, completed=False, running=False)
                    if dat is not None:
                        dat.running = True
                        dat_id = dat.id
                        pid = dat.pid
                        datas.add(dat)
                        last_judged.inc()
            if dat_id is None:
                time.sleep(config.judge.period)
            else:
                runner(dat_id, pid)
                time.sleep(1)
        except Exception as e:
            logger.error(f"Error in queue receiver: {e}")
            logger.debug(traceback.format_exc())
            time.sleep(30)


def enqueue(idx: int) -> int:
    logger.info(f"enqueue {idx}")
    return queue_position.inc()


def rejudge(dat: datas.Submission, msg: str = "wait system test"):
    dat.simple_result = msg
    dat.completed = False
    dat.running = False
    dat.queue_position = enqueue(dat.id)


def init():
    with datas.SessionContext():
        for submission in datas.get_all(datas.Submission, completed=False):
            submission.running = False
            datas.add(submission)
            enqueue(submission.id)
    for _ in range(config.judge.workers):
        multiprocessing.Process(target=queue_receiver).start()
