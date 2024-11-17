import os
import re
from enum import Enum
from pathlib import Path
from re import Pattern

signal_names = {'1': 'SIGHUP', '2': 'SIGINT', '3': 'SIGQUIT', '4': 'SIGILL', '5': 'SIGTRAP', '6': 'SIGABRT',
                '7': 'SIGBUS', '8': 'SIGFPE', '9': 'SIGKILL', '10': 'SIGUSR1', '11': 'SIGSEGV', '12': 'SIGUSR2',
                '13': 'SIGPIPE', '14': 'SIGALRM', '15': 'SIGTERM', '16': 'SIGSTKFLT', '17': 'SIGCHLD', '18': 'SIGCONT',
                '19': 'SIGSTOP', '20': 'SIGTSTP', '21': 'SIGTTIN', '22': 'SIGTTOU', '23': 'SIGURG', '24': 'SIGXCPU',
                '25': 'SIGXFSZ', '26': 'SIGVTALRM', '27': 'SIGPROF', '28': 'SIGWINCH', '29': 'SIGIO', '30': 'SIGPWR',
                '31': 'SIGSYS'}

result_class: dict[str, str] = {
    "OK": "table-success",
    "WA": "table-danger",
    "MLE": "table-warning",
    "TLE": "table-info",
    "OLE": "table-secondary",
    "RE": "table-secondary"
}

exit_codes: dict[str, str] = {
    "1": "您的程式被監控系統中斷，可能是程式無法正常結束所導致",
    "127": "無法分配記憶體",
    "132": "執行了非法的指令",
    "134": "系統呼叫了 abort 函式！",
    "135": "嘗試定址不相符的記憶體位址。",
    "136": "溢位或者除以0的錯誤!!",
    "137": "產生立即終止訊號!!",
    "139": "記憶體區段錯誤！",
    "143": "產生程式中斷訊號！"
}

checker_exit_codes: dict[int, str] = {
    0: "OK",
    1: "WA",
    2: "PE",
    3: "FAIL",
    4: "DIRT",
    7: "POINTS"
}

default_problem_info: dict = {"name": "unknown", "timelimit": "1000", "memorylimit": "256", "testcases": [],
                              "users": [],
                              "statement": {"main": "", "input": "", "output": "", "scoring": "", "interaction": ""},
                              "files": [], "checker_source": ["default", "unknown"], "is_interact": False,
                              "groups": {"default": {"score": 100, "rule": "min", "dependency": []}},
                              "interactor_source": "unknown", "manual_samples": [], "codechecker_source": "unknown",
                              "codechecker_mode": "disabled",
                              "languages": {}, "public_testcase": False, "public_checker": False, "gen_groups": [],
                              "runner_source": {}, "runner_enabled": False, "libraries": []}

# codechecker_mode: disabled public private

email_reg: Pattern = re.compile("^[\\w\\-.]+@([\\w\\-]+\\.)+[\\w-]{2,4}$")

user_id_reg: Pattern = re.compile("^[A-Za-z0-9_]{2,80}$")

problem_id_reg: Pattern = re.compile("^[A-Za-z0-9_]{1,20}$")

email_content: str = """Subject: OrangeJudge verification code ({0})

Your verification code is: {0}
This verification code is valid within 10 minutes"""

page_size: int = 12

polygon_type: dict[str, str] = {"cpp.msys2-mingw64-9-g++17": "C++17", "cpp.g++17": "C++17", "python.3": "Python3"}

polygon_statment: dict[str, str] = {"statement_main": "statement-sections/english/legend.tex",
                                    "statement_input": "statement-sections/english/input.tex",
                                    "statement_output": "statement-sections/english/output.tex",
                                    "statement_interaction": "statement-sections/english/interaction.tex",
                                    "statement_scoring": "statement-sections/english/scoring.tex"}

latex_begin = """\\documentclass[]{article}
\\usepackage{hyperref}
\\usepackage{graphicx}
\\begin{document}
"""
latex_end = "\n\\end{document}"


class Permission(Enum):
    """
    This enumeration represents different levels of permissions in the OrangeJudge system.

    Attributes:
        root (str): Represents the highest level of permission. It is used for the root user.
        admin (str): Represents the permission level of an administrator.
        make_problems (str): Represents the permission level of a problem maker.
    """
    root = "最高管理者"
    admin = "管理者"
    make_problems = "出題者"


default_contest_info: dict = {"name": "unknown", "users": [], "problems": {}, "start": 0, "elapsed": 0, "type": "icpc",
                              "can_register": False, "standing": {"public": True, "start_freeze": 0, "end_freeze": 0},
                              "pretest": "no", "practice": "no", "participants": [], "virtual_participants": {},
                              "penalty": 20}
# pretest: no all last
# practice: no private public
# type icpc ioi ioic cf

danger_html_tags = ("script", "style")

source_file_name = "Main"

runner_source_file_name = "Runner"

data_path = Path("data").absolute()

problem_path = data_path / "problems"

preparing_problem_path = data_path / "preparing_problems"

tmp_path = Path("tmp").absolute()

contest_path = data_path / "contests"

lang_path = Path("langs").absolute()

submission_path = data_path / "submissions"

log_path = data_path / "logs"

testlib = Path("testlib/testlib.h").absolute()

sandbox_path = Path("sandbox").absolute()

judger_url = os.environ.get("JUDGER_URL", "http://localhost:9132")

judge_path = Path("judge").absolute()
