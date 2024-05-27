import os

from modules import tools, constants, datas


def create_contest(name: str, user: datas.User) -> str:
    ccnt = datas.Contest.query.count()
    cidx = ccnt + 1
    while datas.Contest.query.filter_by(cid=str(cidx)).count():
        cidx += 1
    cid = str(cidx)
    info = constants.default_contest_info | {"name": name, "users": [user.username]}
    dat = datas.Contest(id=cidx, cid=cid, name=name, data=info, user=user)
    datas.add(dat)
    os.mkdir("contests/" + cid)
    tools.write_json({}, f"contests/{cid}/standings.json")
    return cid


def init():
    pass
