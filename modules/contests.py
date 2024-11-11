import multiprocessing
from datetime import datetime, timedelta
from multiprocessing import Process
from time import sleep

from cachetools import TTLCache, cached
from flask import abort
from flask_login import current_user
from sqlalchemy.orm.attributes import flag_modified
from werkzeug.datastructures import ImmutableMultiDict

from . import tools, constants, datas, tasks
from .constants import Permission

actions = tools.Switcher()


def create_contest(name: str, user: datas.User) -> str:
    if len(name) > 120:
        abort(400)
    ccnt = datas.Contest.query.count()
    cidx = ccnt + 1
    while datas.Contest.query.filter_by(cid=str(cidx)).count():
        cidx += 1
    cid = str(cidx)
    start_time = datetime.now().replace(second=0, microsecond=0) + timedelta(days=1)
    start_timestamp = start_time.timestamp()
    info = constants.default_contest_info | {"name": name, "users": [user.username], "start": start_timestamp,
                                             "elapsed": 60}
    dat = datas.Contest(id=cidx, cid=cid, name=name, data=info, user=user)
    per = datas.Period(start_time=start_time,
                       end_time=start_time + timedelta(hours=1),
                       ended=False,
                       running=False,
                       contest_id=dat.id,
                       is_virtual=False)
    datas.add(dat, per)
    dat.main_period_id = per.id
    datas.add(dat)
    dat.path.mkdir(parents=True, exist_ok=True)
    tools.write_json({}, dat.path / "standings.json")
    return cid


def calidx(idx: int) -> str:
    s = ""
    if idx >= 26:
        s = calidx(idx // 26 - 1)
        idx %= 26
    return s + chr(ord('A') + idx)


@actions.bind
def add_problem(form: ImmutableMultiDict[str, str], cdat: datas.Contest, dat: dict) -> str:
    pid = form["pid"]
    pdat: datas.Problem = datas.Problem.query.filter_by(pid=pid).first_or_404()
    for idx, obj in dat["problems"].items():
        if obj["pid"] == pid:
            abort(409)
    idx = 0
    while calidx(idx) in dat["problems"]:
        idx += 1
    dat["problems"][calidx(idx)] = {"pid": pid, "name": pdat.name}
    return "index_page"


@actions.bind
def remove_problem(form: ImmutableMultiDict[str, str], cdat: datas.Contest, dat: dict) -> str:
    idx = form["idx"]
    if idx not in dat["problems"]:
        abort(409)
    del dat["problems"][idx]
    return "index_page"


@actions.bind
def add_participant(form: ImmutableMultiDict[str, str], cdat: datas.Contest, dat: dict) -> str:
    user: datas.User = datas.User.query.filter_by(username=form["username"].lower()).first_or_404()
    if user.username in dat["participants"]:
        abort(409)
    dat["participants"].append(user.username)
    return "participants"


@actions.bind
def remove_participant(form: ImmutableMultiDict[str, str], cdat: datas.Contest, dat: dict) -> str:
    user: datas.User = datas.User.query.filter_by(username=form["username"].lower()).first_or_404()
    if user.username not in dat["participants"]:
        abort(409)
    dat["participants"].remove(user.username)
    return "participants"


@actions.bind
def change_settings(form: ImmutableMultiDict[str, str], cdat: datas.Contest, dat: dict) -> str:
    contest_title = form["contest_title"]
    if len(contest_title) < 1 or len(contest_title) > 120:
        abort(400)
    start_time = 0
    try:
        start_time = tools.to_datetime(form["start_time"], second=0, microsecond=0).timestamp()
    except ValueError:
        abort(400)
    if not form["elapsed_time"].isdigit():
        abort(400)
    elapsed_time = int(form["elapsed_time"])
    rule_type = form["rule_type"]
    if rule_type not in ("icpc", "ioi"):
        abort(400)
    pretest_type = form["pretest_type"]
    if pretest_type not in ("all", "last", "no"):
        abort(400)
    practice_type = form["practice_type"]
    if practice_type not in ("no", "private", "public"):
        abort(400)
    register_type = form["register_type"]
    if register_type not in ("no", "yes"):
        abort(400)
    show_standing = form["show_standing"]
    if show_standing not in ("no", "yes"):
        abort(400)
    if not form["freeze_time"].isdigit():
        abort(400)
    freeze_time = int(form["freeze_time"])
    if not form["unfreeze_time"].isdigit():
        abort(400)
    unfreeze_time = int(form["unfreeze_time"])
    if not form["penalty"].isdigit():
        abort(400)
    penalty = int(form["penalty"])
    per: datas.Period = datas.Period.query.get(cdat.main_period_id)
    per.start_time = datetime.fromtimestamp(start_time)
    cdat.name = contest_title
    dat["name"] = contest_title
    dat["start"] = start_time
    dat["elapsed"] = elapsed_time
    dat["type"] = rule_type
    dat["pretest"] = pretest_type
    dat["practice"] = practice_type
    dat["can_register"] = (register_type == "yes")
    dat['standing']['public'] = (show_standing == "yes")
    dat['standing']['start_freeze'] = freeze_time
    dat['standing']['end_freeze'] = unfreeze_time
    dat['penalty'] = penalty
    return "edit"


@actions.bind
def save_order(form: ImmutableMultiDict[str, str], cdat: datas.Contest, dat: dict) -> str:
    order = form["order"].split(",")
    if set(order) != set(dat["problems"]):
        abort(400)
    nw_dict = {}
    arr = sorted(order)
    for k1, k2 in zip(arr, order):
        nw_dict[k1] = dat["problems"][k2]
    dat["problems"] = nw_dict
    return "index_page"


@actions.bind
def send_announcement(form: ImmutableMultiDict[str, str], cdat: datas.Contest, dat: dict) -> str:
    if len(form["title"]) > 80:
        abort(400)
    if len(form["content"]) > 1000:
        abort(400)
    obj = datas.Announcement(time=datetime.now(),
                             title=form["title"],
                             content=form["content"],
                             user=current_user.data,
                             contest=cdat,
                             public=True,
                             question=False)
    datas.add(obj)
    return "index_page"


@actions.bind
def remove_announcement(form: ImmutableMultiDict[str, str], cdat: datas.Contest, dat: dict) -> str:
    idx = tools.to_int(form["id"])
    obj: datas.Announcement = datas.Announcement.query.get_or_404(idx)
    if obj.contest != cdat:
        abort(404)
    datas.delete(obj)
    return "index_page"


@actions.bind
def save_question(form: ImmutableMultiDict[str, str], cdat: datas.Contest, dat: dict) -> str:
    idx = tools.to_int(form["id"])
    obj: datas.Announcement = datas.Announcement.query.get_or_404(idx)
    if obj.contest != cdat:
        abort(404)
    reply = form["content"]
    if len(reply) > 1000:
        abort(400)
    public = form.get("public", "no") == "yes"
    obj.reply = reply
    obj.reply_name = current_user.id
    obj.public = public
    datas.add(obj)
    return "index_page"


@actions.default
def action_not_found(*args):
    abort(404)


def action(form: ImmutableMultiDict[str, str], cdat: datas.Contest):
    with datas.DelayCommit():
        dat = cdat.data
        cid = cdat.cid
        tp = actions.call(form["action"], form, cdat, dat)
        flag_modified(cdat, "data")
        datas.add(cdat)
        if form["action"] == "change_settings":
            for the_per in cdat.periods:
                the_per: datas.Period
                the_per.end_time = the_per.start_time + timedelta(minutes=dat["elapsed"])
            datas.add(*cdat.periods)
    return f"/contest/{cid}#{tp}"


def check_super_access(dat: datas.Contest) -> bool:
    return current_user.is_authenticated and (
            current_user.has(Permission.admin) or current_user.id in dat.data["users"])


def check_access(dat: datas.Contest):
    per: datas.Period = datas.Period.query.get(dat.main_period_id)
    if per is None:
        abort(409)
    if check_super_access(dat):
        return
    if current_user.is_authenticated:
        if current_user.id in dat.data["participants"]:
            if per.is_running():
                return
            if per.is_over() and dat.data["practice"] != "no":
                return
    if dat.data["practice"] == "public" and per.is_over():
        return
    abort(403)


def check_status(dat: datas.Contest) -> tuple[str, int, bool]:
    per: datas.Period = datas.Period.query.get_or_404(dat.main_period_id)
    if current_user.is_authenticated:
        if current_user.id in dat.data["virtual_participants"]:
            vir_per: datas.Period = datas.Period.query.get(dat.data["virtual_participants"][current_user.id])
            if vir_per is None:
                abort(409)
            if not vir_per.is_started():
                return "waiting_virtual", vir_per.start_time.timestamp(), False
            if vir_per.is_running():
                return "running_virtual", vir_per.end_time.timestamp(), True
        if current_user.id in dat.data["participants"]:
            if not per.is_started():
                return "waiting", per.start_time.timestamp(), False
            if per.is_running():
                return "running", per.end_time.timestamp(), True
            if per.is_over() and dat.data["practice"] != "no":
                return "practice", 0, True
        if check_super_access(dat):
            return "testing", 0, True
        if per.is_over() and dat.data["practice"] == "public":
            return "practice", 0, True
    if dat.data["practice"] == "public" and per.is_over():
        return "guest", 0, True
    return "guest", 0, False


def check_period(dat: datas.Contest) -> int:
    main_per: datas.Period = datas.Period.query.get_or_404(dat.main_period_id)
    if current_user.id in dat.data["participants"] and main_per.is_running():
        return dat.main_period_id
    if current_user.id in dat.data["virtual_participants"]:
        per_id = dat.data["virtual_participants"][current_user.id]
        cur_per: datas.Period = datas.Period.query.get_or_404(per_id)
        if cur_per.is_running():
            return per_id
    return 0


standing_lock = multiprocessing.Lock()


@cached(cache=TTLCache(maxsize=20, ttl=10), lock=standing_lock)
def get_standing(cid: str):
    cdat: datas.Contest = datas.Contest.query.filter_by(cid=cid).first_or_404()
    ret = []
    mp = {}
    rmp = {}
    for k, v in cdat.data["problems"].items():
        rmp[v["pid"]] = k
    for dat in cdat.submissions:
        dat: datas.Submission
        if dat.completed and "group_results" in dat.result:
            if dat.user_id not in mp:
                mp[dat.user_id] = dat.user.display_name
            scores = {k: v["gainscore"] for k, v in dat.result["group_results"].items()}
            ret.append({"user": mp[dat.user_id],
                        "pid": rmp[dat.pid],
                        "scores": scores,
                        "total_score": dat.result["total_score"],
                        "time": dat.time.timestamp(),
                        "pretest": dat.just_pretest,
                        "per": dat.period_id})
    pers = []
    for per in cdat.periods:
        per: datas.Period
        pers.append({"start_time": per.start_time.timestamp(),
                     "judging": per.judging,
                     "idx": per.id})
    return {"submissions": ret,
            "rule": cdat.data["type"],
            "pids": list(cdat.data["problems"].keys()),
            "penalty": cdat.data["penalty"],
            "pers": pers,
            "main_per": cdat.main_period_id,
            "participants": cdat.data["participants"],
            "virtual_participants": cdat.data["virtual_participants"]}


def break_result(dat: datas.Submission):
    dat.simple_result = "ignored"
    dat.result["total_score"] = 0
    if "group_results" in dat.result:
        for k in dat.result["group_results"]:
            dat.result["group_results"][k]["gainscore"] = 0
    flag_modified(dat, "result")


def resubmit(dat: datas.Submission):
    dat.simple_result = "wait system test"
    dat.completed = False
    dat.queue_position = tasks.enqueue(dat.id)


def contest_worker():
    while True:
        with datas.DelayCommit():
            for dat in datas.Period.query.filter_by(running=True):
                dat: datas.Period
                if dat.is_over():
                    dat.running = False
                    dat.ended = True
                    cdat: datas.Contest = dat.contest
                    pretest = cdat.data["pretest"]
                    if pretest != "no":
                        submissions = dat.submissions.filter_by(just_pretest=True).all()
                        dic: dict[tuple[int, str], datas.Submission] = {}
                        datas.add(*submissions)
                        for submission in submissions:
                            submission: datas.Submission
                            submission.just_pretest = False
                            key = (submission.user_id, submission.pid)
                            if submission.simple_result.lower() not in ("jc", "ce"):
                                break_result(submission)
                                if pretest == "all":
                                    resubmit(submission)
                                elif submission.simple_result.lower() == 'pretest passed':
                                    dic[key] = submission
                        if pretest == "last":
                            for v in dic.values():
                                resubmit(v)
                        datas.add(*submissions)
                datas.add(dat)
        sleep(5)
        with datas.DelayCommit():
            for dat in datas.Period.query.filter_by(running=False, ended=False):
                dat: datas.Period
                if dat.is_running():
                    dat.running = True
                    dat.judging = True
                    datas.add(dat)
        sleep(5)
        with datas.DelayCommit():
            for dat in datas.Period.query.filter_by(running=False, ended=True, judging=True):
                dat: datas.Period
                if dat.submissions.filter_by(completed=False).count() == 0:
                    dat.judging = False
                    datas.add(dat)
        sleep(5)
        with datas.DelayCommit():
            for dat in datas.Period.query.filter_by(running=False, ended=True, judging=False):
                dat: datas.Period
                if not dat.is_started():
                    dat.ended = False
                    datas.add(dat)
        sleep(5)


def init():
    Process(target=contest_worker).start()
