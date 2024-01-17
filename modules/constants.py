import re

result_class = {
    "OK": "table-success",
    "WA": "table-danger",
    "MLE": "table-warning",
    "TLE": "table-info",
    "OLE": "table-secondary",
    "RE": "table-secondary"
}

exit_codes = {
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

judge_exit_codes = {
    0: "OK",
    1: "WA",
    2: "PE",
    3: "FAIL",
    4: "DIRT",
    7: "POINTS"
}

lxc_name = "lxc-test"

default_problem_info = {"name": "unknow", "timelimit": "1000", "memorylimit": "256", "testcases": [], "users": [],
                        "statement": {"main": "", "input": "", "output": "", "score": ""}, "files": [],
                        "checker_source": ["default", "unknow"], "is_interact": False, "role": "private",
                        "groups": {"default": {"score": 100, "rule": "min"}}, "interactor_source": ["default", "unknow"]}

email_reg = re.compile("^[\\w\\-\\.]+@([\\w\\-]+\\.)+[\\w-]{2,4}$")

user_id_reg = re.compile("^[A-Za-z0-9_]+$")

email_content = """Subject: OrangeJudge verification code ({0})

Your verification code is: {0}
This verification code is valid within 10 minutes"""
