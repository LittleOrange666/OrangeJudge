import json
import os
from flask import abort, render_template, redirect, request, send_file
from flask_login import login_required, current_user
from pygments import highlight, lexers
from pygments.formatters import HtmlFormatter
from werkzeug.utils import secure_filename
from modules import tools, server, constants, executing, tasks

app = server.app

prepares = {k: lexers.get_lexer_by_name(k) for lexer in lexers.get_all_lexers() for k in lexer[1]}

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route('/problems', methods=['GET'])
def problems():
    return render_template("problems.html", problems=tools.read_json("data/public_problems.json"))


@app.route('/test', methods=['GET', 'POST'])
@login_required
def test():
    if request.method == 'GET':
        return render_template("test.html", langs=executing.langs.keys())
    else:
        lang = request.form["lang"]
        code = request.form["code"].replace("\n\n", "\n")
        inp = request.form["input"]
        if not inp.endswith("\n"):
            inp += "\n"
        if lang not in executing.langs:
            abort(404)
        ext = executing.langs[lang].data["source_ext"]
        idx = tasks.create_submission()
        if tools.elapsed(current_user.folder, "submissions") < 5:
            abort(429)
        tools.append(idx + "\n", current_user.folder, "submissions")
        tools.write(code, f"submissions/{idx}/a{ext}")
        tools.write(inp, f"submissions/{idx}/in.txt")
        dat = {"type": "test", "source": "a" + ext, "infile": "in.txt", "outfile": "out.txt", "lang": lang,
               "user": current_user.id, "time": tools.get_timestring()}
        tools.write_json(dat, f"submissions/{idx}/info.json")
        tasks.submissions_queue.put(idx)
        return redirect("/submission/" + idx)


@app.route("/submit", methods=['POST'])
@login_required
def submit():
    lang = request.form["lang"]
    code = request.form["code"].replace("\n\n", "\n")
    pid = request.form["pid"]
    pid = secure_filename(pid)
    if not tools.exists("problems", pid, "info.json"):
        abort(404)
    if lang not in executing.langs:
        abort(404)
    ext = executing.langs[lang].data["source_ext"]
    idx = tasks.create_submission()
    if tools.elapsed(current_user.folder, "submissions") < 5:
        abort(429)
    tools.append(idx + "\n", current_user.folder, "submissions")
    tools.write(code, f"submissions/{idx}/a{ext}")
    dat = {"type": "problem", "source": "a" + ext, "lang": lang, "pid": pid, "user": current_user.id,
           "time": tools.get_timestring()}
    tools.write_json(dat, f"submissions/{idx}/info.json")
    tasks.submissions_queue.put(idx)
    return redirect("/submission/" + idx)


@app.route("/submission/<idx>", methods=['GET'])
@login_required
def submission(idx):
    idx = secure_filename(idx)
    path = "submissions/" + idx
    if not os.path.isdir(path):
        abort(404)
    dat = tools.read_json(path, "info.json")
    lang = dat["lang"]
    source = tools.read(path, dat["source"])
    source = highlight(source, prepares[executing.langs[lang].name], HtmlFormatter())
    completed = os.path.exists(path + "/completed")
    ce_msg = tools.read_default(path, "ce_msg.txt")
    ret = ""
    match dat["type"]:
        case "test":
            if not current_user.has("admin") and dat["user"] != current_user.id:
                abort(403)
            inp = tools.read_default(path, dat["infile"])
            out = tools.read_default(path, dat["outfile"])
            result = tools.read_default(path, "results")
            err = tools.read_default(path, "stderr.txt")
            ret = render_template("submission/test.html", lang=lang, source=source, inp=inp,
                                  out=out, completed=completed, result=result, pos=tasks.get_queue_position(idx),
                                  ce_msg=ce_msg, je=dat.get("JE", False), logid=dat.get("log_uuid", ""), err=err)
        case "problem":
            pid = dat["pid"]
            problem_path = f"problems/{pid}/"
            group_results = {}
            problem_info = tools.read_json(problem_path, "info.json")
            if not current_user.has("admin") and dat["user"] != current_user.id and current_user.id not in problem_info[
                "users"]:
                abort(403)
            result = {}
            if completed and not dat.get("JE", False):
                result_data = tools.read_json(path, "results.json")
                result["CE"] = result_data["CE"]
                results = result_data["results"]
                result["protected"] = protected = result_data.get("protected", False)
                if not protected:
                    for i in range(len(results)):
                        tcl = len(problem_info["testcases"])
                        it = i if i < tcl else i - tcl
                        test_type = "testcases" if i < tcl else "testcases_gen"
                        results[i] |= problem_info[test_type][it]
                        if results[i]["result"] != "SKIP":
                            results[i]["in"] = tools.read(f"{path}/testcases/{i}.in")
                            results[i]["out"] = tools.read(f"{path}/testcases/{i}.ans")
                        else:
                            results[i]["in"] = results[i]["out"] = ""
                        if results[i].get("has_output", False):
                            results[i]["user_out"] = tools.read(f"{path}/testcases/{i}.out")
                result["results"] = results
                if "group_results" in result_data:
                    gpr = result_data["group_results"]
                    if len(gpr) > 0 and type(next(iter(gpr.values()))) == dict:
                        group_results = gpr
                        for o in group_results.values():
                            o["class"] = constants.result_class.get(o["result"], "")
                if "total_score" in result_data:
                    result["total_score"] = result_data["total_score"]
            ret = render_template("submission/problem.html", lang=lang, source=source, completed=completed,
                                  pname=problem_info["name"], result=result, enumerate=enumerate,
                                  group_results=group_results, pid=pid, pos=tasks.get_queue_position(idx),
                                  ce_msg=ce_msg, je=dat.get("JE", False), logid=dat.get("log_uuid", ""))
        case _:
            abort(404)
    return ret


@app.route("/problem/<idx>", methods=['GET'])
def problem(idx):
    idx = secure_filename(idx)
    path = "problems/" + idx
    if not os.path.isdir(path):
        abort(404)
    dat = tools.read_json(path, "info.json")
    if not dat.get("public", False):
        if not current_user.is_authenticated:
            abort(403)
        if not current_user.has("admin") and current_user.id not in dat.get("users", []):
            abort(403)
    statement = tools.read(path, "statement.html")
    lang_exts = json.dumps({k: v.data["source_ext"] for k, v in executing.langs.items()})
    samples = dat.get("manual_samples", []) + [[tools.read(path, k, o["in"]), tools.read(path, k, o["out"])]
                                               for k in ("testcases", "testcases_gen") for o in dat.get(k, []) if
                                               o.get("sample", False)]
    return render_template("problem.html", dat=dat, statement=statement,
                           langs=executing.langs.keys(), lang_exts=lang_exts, pid=idx,
                           preview=False, samples=enumerate(samples))


@app.route("/problem_file/<idx>/<filename>", methods=['GET'])
def problem_file(idx, filename):
    idx = secure_filename(idx)
    filename = secure_filename(filename)
    dat = tools.read_json("problems", idx, "info.json")
    if not dat.get("public", False):
        if not current_user.is_authenticated:
            abort(403)
        if not current_user.has("admin") and current_user.id not in dat["users"]:
            abort(403)
    target = f"problems/{idx}/public_file/{filename}"
    if not os.path.isfile(target):
        abort(404)
    return send_file(target)


@app.route("/my_submissions", methods=['GET'])
@login_required
def my_submissions():
    submission_list = tools.read(current_user.folder, "submissions").split()
    submit_cnt = len(submission_list)
    page_cnt = (submit_cnt - 1) // constants.page_size + 1
    out = []
    page = request.args.get("page", "1")
    if not page.isdigit():
        abort(404)
    page_idx = int(page)
    if page_idx <= 0 or page_idx > page_cnt:
        abort(404)
    got_data = submission_list[
               max(0, submit_cnt - constants.page_size * page_idx):submit_cnt - constants.page_size * (page_idx - 1)]
    for idx in reversed(got_data):
        o = {"name": idx, "time": "blank", "result": "blank"}
        if not tools.exists(f"submissions/{idx}/info.json"):
            continue
        dat = tools.read_json(f"submissions/{idx}/info.json")
        if "time" in dat:
            o["time"] = dat["time"]
        if not os.path.isfile(f"submissions/{idx}/results.json"):
            o["result"] = "waiting"
        else:
            result = tools.read_json(f"submissions/{idx}/results.json")
            if "simple_result" in result:
                o["result"] = result["simple_result"]
        if dat["type"] == "test":
            o["source"] = "/test"
            o["source_name"] = "Simple Testing"
        else:
            o["source"] = "/problem/" + dat["pid"]
            source_dat = tools.read_json(f"problems/{dat['pid']}/info.json")
            o["source_name"] = source_dat["name"]
        out.append(o)
    displays = [1, page_cnt]
    displays.extend(range(max(2, page_idx - 2), min(page_cnt, page_idx + 2) + 1))
    return render_template("my_submissions.html", submissions=out, page_cnt=page_cnt, page_idx=page_idx,
                           show_pages=sorted(set(displays)))