import re
from re import Pattern

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

judge_exit_codes: dict[int, str] = {
    0: "OK",
    1: "WA",
    2: "PE",
    3: "FAIL",
    4: "DIRT",
    7: "POINTS"
}

lxc_name: str = "lxc-test"

default_problem_info: dict = {"name": "unknown", "timelimit": "1000", "memorylimit": "256", "testcases": [],
                              "users": [],
                              "statement": {"main": "", "input": "", "output": "", "scoring": "", "interaction": ""},
                              "files": [], "checker_source": ["default", "unknown"], "is_interact": False,
                              "public": False, "groups": {"default": {"score": 100, "rule": "min"}},
                              "interactor_source": "unknown", "manual_samples": []}

email_reg: Pattern = re.compile("^[\\w\\-.]+@([\\w\\-]+\\.)+[\\w-]{2,4}$")

user_id_reg: Pattern = re.compile("^[A-Za-z0-9_]{2,80}$")

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

permissions: dict[str, str] = {"admin": "管理者", "make_problems": "出題者"}

default_contest_info: dict = {"name": "unknown", "users": [], "problems": {}, "start": 0, "elapsed": 0, "type": "icpc",
                              "can_register": False, "standing": {"public": True, "start_freeze": 0, "end_freeze": 0},
                              "pretest": "no", "practice": "no", "participants": [], "virtual_participants": {}}
# pretest: no all last
# practice: no private public
# type icpc ioi ioic cf
