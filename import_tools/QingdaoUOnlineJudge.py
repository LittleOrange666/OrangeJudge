import html
import json
import random
import re
import os
import shutil
import string

import requests
from pyzipper import AESZipFile
from pyzipper.zipfile_aes import AESZipInfo

info_file = "qindaou_info.json"


class QingdaoUOJ:

    def __init__(self):
        self.info = {}
        if os.path.exists(info_file):
            with open(info_file) as f:
                self.info = json.load(f)
        if "url" not in self.info:
            self.info["url"] = input("Please input the url of OJ: ").strip()
        if "account" not in self.info:
            self.info["account"] = input("Please input the account of OJ: ").strip()
        if "password" not in self.info:
            self.info["password"] = input("Please input the password of OJ: ").strip()
        url = self.info["url"]
        if url.endswith("/"):
            url = url[:-1]
        if not url.startswith("http"):
            url = "https://" + url
        self.info["url"] = url
        self.url: str = url
        self.cookie: str | None = None
        if "cookie" in self.info:
            self.cookie = self.info["cookie"]
            if not self.check_login():
                self.login()
                self.info["cookie"] = self.cookie
        else:
            self.login()
            self.info["cookie"] = self.cookie
        with open(info_file, "w") as f:
            json.dump(self.info, f)

    def check_login(self):
        dat = self.get_data("api/profile")
        return dat is not None

    def login(self):
        account = self.info["account"]
        password = self.info["password"]
        login_url = self.url + "/api/login"
        session = requests.Session()
        csrf_token = "".join(random.choices(string.ascii_letters + string.digits, k=64))
        session.cookies.set("csrftoken", csrf_token)
        headers = {
            "Content-Type": "application/json",
            "Referer": self.url,
            "Origin": self.url,
            "x-csrftoken": csrf_token
        }
        res = session.post(login_url, json={"username": account, "password": password}, headers=headers)
        print(res.text)
        cookie = session.cookies.get_dict()
        print(cookie)
        self.cookie = "; ".join([f"{k}={v}" for k, v in cookie.items()])

    def get_cookie(self) -> str:
        if self.cookie is None:
            raise ValueError("cookie can not be None here")
        return self.cookie

    def do_get(self, path: str) -> requests.Response:
        if not path.startswith("/") and len(path) > 0:
            path = "/" + path
        res = requests.get(self.url + path, headers={"Cookie": self.get_cookie()})
        if not res.ok:
            raise requests.exceptions.RequestException(f"request to {res.url} fail, error code={res.status_code}")
        return res

    def get_data(self, path: str):
        res = self.do_get(path)
        dat = res.json()
        if dat["error"]:
            if dat['data'] == 'Please login first.':
                self.login()
                return self.get_data(path)
            raise Exception(f"request to {res.url} fail, {dat['data']}")
        return dat["data"]

    def get_pid(self):
        print("請問要用的輸入方式為：")
        print("1. public problem id")
        print("2. contest id + problem id")
        print("3. inner id")
        choice = input("請輸入選項(1/2/3/q): ").strip()
        if choice == "1":
            pid = input("請輸入 public problem id: ").strip()
            res = self.get_data("/api/problem?problem_id="+pid)
            return str(res["id"])
        elif choice == "2":
            contest_id = input("請輸入 contest id: ").strip()
            problem_id = input("請輸入 problem id: ").strip()
            res = self.get_data(f"/api/contest/problem?contest_id={contest_id}&problem_id={problem_id}")
            return str(res["id"])
        elif choice == "3":
            inner_id = input("請輸入 inner id: ").strip()
            return inner_id
        elif choice.lower() == "q":
            print("退出程序")
            exit(0)
        else:
            print("無效的選項，請重新輸入。")
            return self.get_pid()


def nl(s: str) -> str:
    if not s.endswith("\n"):
        return s + "\n"
    return s


def main():
    oj = QingdaoUOJ()

    while True:
        pid = oj.get_pid()
        print("pid=", pid)
        link1 = "/api/admin/test_case?problem_id=" + pid
        link2 = "/api/admin/problem?id=" + pid
        testcase = f"{pid}_testcase.zip"
        data_file = f"{pid}_data.json"
        output = f"problem_{pid}.zip"
        res1 = oj.do_get(link1)
        with open(testcase, "wb") as f:
            f.write(res1.content)
        res2 = oj.do_get(link2)
        with open(data_file, "wb") as f:
            f.write(res2.content)
        data = res2.json()
        out_data = {}
        if data["error"]:
            print(f"{pid} 下載失敗: {data['error']}")
            continue
        data = data["data"]
        out_data["name"] = data["title"]
        out_data["timelimit"] = data["time_limit"]
        out_data["memorylimit"] = data["memory_limit"]
        out_data["statement"] = {"main": data["description"],
                                 "input": data["input_description"],
                                 "output": data["output_description"],
                                 "scoring": data["hint"],
                                 "interaction": "",
                                 "type": "md"}
        testcases = []
        gps = {}
        for obj in data["test_case_score"]:
            if obj["score"] not in gps:
                gps[obj["score"]] = {"cnt": 0, "name": "group_" + str(len(gps) + 1)}
            ptr = gps[obj["score"]]
            ptr["cnt"] += 1
            gpn = ptr["name"]
            testcases.append({"in_file": obj["input_name"],
                              "out_file": obj["output_name"],
                              "sample": False,
                              "pretest": False,
                              "group": gpn})
        out = AESZipFile(output, "w")
        for i, obj in enumerate(data["samples"]):
            testcases.append({"in_file": f"sample_{i}.in",
                              "out_file": f"sample_{i}.out",
                              "sample": True,
                              "pretest": True,
                              "group": "sample"})
            out.writestr(f"testcases/sample_{i}.in", nl(obj["input"]))
            out.writestr(f"testcases/sample_{i}.out", nl(obj["output"]))
        groups = {"default": {
            "score": 0,
            "rule": "min",
            "dependency": []
        },
            "sample": {
                "score": 0,
                "rule": "min",
                "dependency": []
            }
        }
        for k, v in gps.items():
            groups[v["name"]] = {
                "score": k * v["cnt"],
                "rule": "avg",
                "dependency": ["sample"]
            }
        out_data["groups"] = groups
        out_data["testcases"] = testcases
        for k in out_data["statement"]:
            txt = out_data["statement"][k]
            for s in re.findall('/public/upload/[^"]*"', txt):
                fn = s[15:-1]
                down = oj.do_get(f"/public/upload/{fn}")
                out.writestr(f"public_file/{fn}", down.content)
                txt = txt.replace(s, f'{fn}"')
            txt = html.unescape(
                txt.replace("</p><p>", "\n").replace("<br />", "\n").replace("<p>", "").replace("</p>", ""))
            out_data["statement"][k] = txt
        out.writestr("info.json", json.dumps(out_data))
        tc_file = AESZipFile(f"{pid}_testcase.zip", "r")
        for file in tc_file.filelist:
            file: AESZipInfo
            tc_file.extract(file, f"{pid}_testcase")
            out.write(f"{pid}_testcase/{file.filename}", f"testcases/{file.filename}")
        tc_file.close()
        out.close()
        os.remove(testcase)
        os.remove(data_file)
        shutil.rmtree(f"{pid}_testcase", ignore_errors=True)
        print(f"Problem {pid} exported to {output} successfully.")


if __name__ == "__main__":
    main()
