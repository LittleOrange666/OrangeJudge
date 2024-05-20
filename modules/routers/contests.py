from flask import abort, render_template, request
from flask_login import login_required, current_user
from modules import tools, server, login, constants, contests

app = server.app


@app.route("/contests", methods=["GET"])
def contests_list():
    contest_list = tools.read("data/public_contests").split()
    contest_cnt = len(contest_list)
    page_cnt = max((contest_cnt - 1) // constants.page_size + 1, 1)
    out = []
    page = request.args.get("page", "1")
    if not page.isdigit():
        abort(404)
    page_idx = int(page)
    if page_idx <= 0 or page_idx > page_cnt:
        abort(404)
    got_data = contest_list[
               max(0, contest_cnt - constants.page_size * page_idx):contest_cnt - constants.page_size * (page_idx - 1)]
    for idx in got_data:
        o = tools.read_json("contests", idx, "info.json")
        o["idx"] = idx
        out.append(o)
    displays = [1, page_cnt]
    displays.extend(range(max(2, page_idx - 2), min(page_cnt, page_idx + 2) + 1))
    return render_template("contests.html", contests=out, page_cnt=page_cnt, page_idx=page_idx,
                           show_pages=sorted(set(displays)))


@app.route("/create_contest", methods=["POST"])
@login_required
def create_contest():
    login.check_user("make_problems")
    name = request.form["contest_name"]
    if not name:
        abort(400)
    idx = contests.create_contest(name, current_user.id)
    return "/contest/" + idx, 200


@app.route("/contest/<idx>", methods=["GET"])
def contest_page(idx):
    info = tools.read_json("contests", idx, "info.json")
    return render_template("contest.html", data=info)