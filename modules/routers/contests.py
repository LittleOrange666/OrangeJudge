import json

from flask import abort, render_template, request
from flask_login import login_required, current_user

from modules import server, login, constants, contests, datas, tools, executing

app = server.app


@app.route("/contests", methods=["GET"])
def contests_list():
    public_contests = datas.Contest.query
    contest_cnt = public_contests.count()
    page_cnt = max(1, (contest_cnt - 1) // constants.page_size + 1)
    page = request.args.get("page", "1")
    if not page.isdigit():
        abort(404)
    page_idx = int(page)
    if page_idx <= 0 or page_idx > page_cnt:
        abort(404)
    got_data = public_contests.slice(constants.page_size * (page_idx - 1),
                                     min(contest_cnt, constants.page_size * page_idx)).all()
    displays = [1, page_cnt]
    displays.extend(range(max(2, page_idx - 2), min(page_cnt, page_idx + 2) + 1))
    return render_template("contests.html", contests=got_data, page_cnt=page_cnt, page_idx=page_idx,
                           show_pages=sorted(set(displays)))


@app.route("/create_contest", methods=["POST"])
@login_required
def create_contest():
    login.check_user("make_problems")
    name = request.form.get("contest_name")
    if not name or len(name) > 120:
        abort(400)
    idx = contests.create_contest(name, current_user.data)
    return "/contest/" + idx, 200


@app.route("/contest/<idx>", methods=["GET"])
def contest_page(idx):
    dat: datas.Contest = datas.Contest.query.filter_by(cid=idx).first_or_404()
    info = dat.data
    can_edit = current_user.is_authenticated and current_user.id in info["users"]
    return render_template("contest.html", cid=idx, data=info, can_edit=can_edit)


@app.route("/contest/<cid>/<pid>", methods=["GET"])
def contest_problem(cid, pid):
    cdat: datas.Contest = datas.Contest.query.filter_by(cid=cid).first_or_404()
    info = cdat.data
    idx = ""
    for obj in info["problems"]:
        if obj["idx"] == pid:
            idx = obj["pid"]
            break
    else:
        abort(404)
    pdat: datas.Problem = datas.Problem.query.filter_by(pid=idx).first_or_404()
    path = "problems/" + idx
    dat = pdat.data
    statement = tools.read(path, "statement.html")
    lang_exts = json.dumps({k: v.data["source_ext"] for k, v in executing.langs.items()})
    samples = dat.get("manual_samples", []) + [[tools.read(path, k, o["in"]), tools.read(path, k, o["out"])]
                                               for k in ("testcases", "testcases_gen") for o in dat.get(k, []) if
                                               o.get("sample", False)]
    return render_template("problem.html", dat=dat, statement=statement,
                           langs=executing.langs.keys(), lang_exts=lang_exts, pid=idx,
                           preview=False, samples=enumerate(samples), is_contest=True, cid=cid,
                           cname=cdat.name, pidx=pid)


@app.route("/contest_action", methods=['POST'])
@login_required
def contest_action():
    idx = request.form["cid"]
    cdat = datas.Contest.query.filter_by(cid=idx).first_or_404()
    if not current_user.id in cdat.data["users"]:
        abort(403)
    return contests.action(request.form, cdat)
