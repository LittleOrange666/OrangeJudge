import os

from modules import tools, constants


def create_contest(name: str, user: str) -> str:
    with tools.File("data/contest_count") as f:
        idx = int(f.read())
        idx = str(idx + 1)
        f.write(idx)
    os.mkdir("contests/" + idx)
    path = "contests/" + idx
    info = constants.default_contest_info | {"name": name, "users": [user]}
    tools.write_json(info, path, "info.json")
    tools.write_json({}, path, "submissions")
    tools.write_json({}, path, "standings.json")
    tools.append(idx + "\n", "data/public_contests")
    return idx
