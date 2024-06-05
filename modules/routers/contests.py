from flask import abort, render_template, request
from flask_login import login_required, current_user

from modules import server, login, constants, contests, datas

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
    dat: datas.Problem = datas.Contest.query.filter_by(cid=idx).first_or_404()
    info = dat.data
    return render_template("contest.html", cid=idx, data=info)
