import html
import json
import re
import os

import requests
from pyzipper import AESZipFile
from pyzipper.zipfile_aes import AESZipInfo


def nl(s: str) -> str:
    if not s.endswith("\n"):
        return s + "\n"
    return s


def main():
    web = ""
    if os.path.exist("web.txt"):
        with open("web.txt") as f:
            web = f.read()
    while not web:
        web = input("請輸入網址: ").strip()
    if web.endswith("/"):
        web = web[:-1]
    if not web.startswith("http"):
        web = "https://" + web
    cookie = ""
    if os.path.exist("cookie.txt"):
        with open("cookie.txt") as f:
            cookie = f.read()
    while not cookie:
        cookie = input("請輸入Cookie: ").strip()

    def get(link):
        print("GET", link)
        return requests.get(link, headers={"Cookie": cookie})

    while True:
        pid = input("請輸入題目ID(流水號的那個，不是Display ID): ")
        link1 = web + "/api/admin/test_case?problem_id=" + pid
        link2 = web + "/api/admin/problem?id=" + pid
        testcase = f"{pid}_testcase.zip"
        data_file = f"{pid}_data.json"
        output = f"problem_{pid}.zip"
        res1 = get(link1)
        with open(testcase, "wb") as f:
            f.write(res1.content)
        res2 = get(link2)
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
            testcases.append({"in": obj["input_name"],
                              "out": obj["output_name"],
                              "sample": False,
                              "pretest": False,
                              "group": gpn})
        out = AESZipFile(output, "w")
        for i, obj in enumerate(data["samples"]):
            testcases.append({"in": f"sample_{i}.in",
                              "out": f"sample_{i}.out",
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
                down = get(f"{web}/public/upload/{fn}")
                out.writestr(f"public_file/{fn}", down.content)
                txt = txt.replace(s, f'{fn}"')
            txt = html.unescape(txt.replace("</p><p>", "\n").replace("<br />", "\n").replace("<p>", "").replace("</p>", ""))
            out_data["statement"][k] = txt
        out.writestr("info.json", json.dumps(out_data))
        tc_file = AESZipFile(f"{pid}_testcase.zip", "r")
        for file in tc_file.filelist:
            file: AESZipInfo
            tc_file.extract(file, f"{pid}_testcase")
            out.write(f"{pid}_testcase/{file.filename}", f"testcases/{file.filename}")
        tc_file.close()
        out.close()


if __name__ == "__main__":
    main()
