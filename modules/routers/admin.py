"""
OrangeJudge, a competitive programming platform

Copyright (C) 2024-2026 LittleOrange666 (orangeminecraft123@gmail.com)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
import csv
import json
import os
import threading
import time
import traceback
import uuid
from io import BytesIO, TextIOWrapper

from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from limits import parse
from openpyxl import load_workbook

from .. import tools, server, datas, login, config, constants
from ..objs import Permission

app = server.app


def _placeholder_email(username: str) -> str:
    return uuid.uuid5(uuid.NAMESPACE_DNS, username).hex + "@placeholder.com"


def update_user():
    password = request.form.get("password", "")
    if password and len(password) < 6:
        server.custom_abort(400, "Password must be at least 6 characters long")
    display_name = request.form["display_name"]
    if len(display_name) < 1 or len(display_name) > 120:
        server.custom_abort(400, "Display name length invalid")
    with datas.SessionContext():
        user: datas.User = datas.first(datas.User, username=request.form["username"])
        if user is None:
            server.custom_abort(404, "User not found")
        user.display_name = display_name
        if password:
            user.password_sha256_hex = login.try_hash(password)
        perms = [perm for perm in user.permission_list() if perm]
        new_perms = request.form["permissions"].split(";")
        for perm_name in ("admin", "make_problems"):
            if perm_name in new_perms:
                if perm_name not in perms:
                    perms.append(perm_name)
            else:
                if perm_name in perms:
                    perms.remove(perm_name)
        user.permissions = ";".join(perms)
        datas.add(user)
    return "OK", 200


def parse_user() -> dict:
    """
    Parse an uploaded .csv/.xlsx file into a list of users to create.

    Returns:
        dict: {"users": [[username, password, email, display_name], ...], "existed": [[username, email], ...]}
    """
    file = request.files.get("file")
    if not file or file.filename == "":
        server.custom_abort(400, "No file provided")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".xlsx", ".csv"):
        server.custom_abort(400, "Unsupported file type")
    try:
        in_memory_file = BytesIO(file.stream.read())
        if ext == ".xlsx":
            wb = load_workbook(in_memory_file, data_only=True)
            ws = wb.active
            arr = [["" if cell.value is None else str(cell.value) for cell in row] for row in ws.iter_rows()]
        else:
            wrapper = TextIOWrapper(in_memory_file, encoding="utf-8-sig")
            reader = csv.reader(wrapper)
            arr = [[cell for cell in row] for row in reader]
    except Exception as e:
        traceback.print_exception(e)
        server.custom_abort(400, "Failed to read file")
    if len(arr) < 1:
        server.custom_abort(400, "No data found")
    title = [cell.strip().lower() for cell in arr[0]]
    i0 = 0
    i1 = 1
    i2 = 2
    i3 = 3
    if "username" in title and "password" in title:
        i0 = title.index("username")
        i1 = title.index("password")
        if "email" in title:
            i2 = title.index("email")
        else:
            i2 = -1
        if "display_name" in title:
            i3 = title.index("display_name")
        else:
            i3 = -1
        arr = arr[1:]
    out = []
    existed = []
    seen = set()
    for row in arr:
        if len(row) < 2:
            continue
        username = row[i0].strip().lower() if len(row) > i0 else ""
        password = row[i1].strip() if len(row) > i1 else ""
        email = row[i2].strip() if 0 <= i2 < len(row) else ""
        display_name = row[i3].strip() if 0 <= i3 < len(row) else ""
        if not display_name:
            display_name = username
        if not username or not password or username in seen:
            continue
        seen.add(username)
        if datas.count(datas.User, username=username) > 0 or (email and datas.count(datas.User, email=email) > 0):
            existed.append([username, email])
            continue
        out.append([username, password, email, display_name])
    if len(out) < 1 and len(existed) < 1:
        server.custom_abort(400, "No valid user data found")
    return {"users": out, "existed": existed}


def create_users() -> int:
    """
    Create users from the JSON list in form field "users".

    Returns:
        int: The number of created users.
    """
    dat = request.form["users"]
    try:
        users = json.loads(dat)
    except json.JSONDecodeError:
        server.custom_abort(400, "Invalid JSON data")
    if not isinstance(users, list) or len(users) < 1:
        server.custom_abort(400, "No valid user data found")
    created = 0
    for user in users:
        if not isinstance(user, list) or len(user) < 2:
            continue
        username = str(user[0]).strip().lower()
        password = str(user[1]).strip()
        email = str(user[2]).strip() if len(user) > 2 else ""
        if not email:
            email = _placeholder_email(username)
        display_name = str(user[3]).strip() if len(user) > 3 else ""
        if not display_name:
            display_name = username
        if not username or not password:
            continue
        if constants.user_id_reg.match(username) is None:
            continue
        if datas.count(datas.User, username=username) > 0 or datas.count(datas.User, email=email) > 0:
            continue
        login.create_account(email, username, password, display_name)
        created += 1
    return created


def is_valid_limit_string(limit_str: str) -> bool:
    try:
        parse(limit_str)
        return True
    except Exception:
        return False


def update_config():
    config_fields = config.get_fields()
    dat_str = request.form["config"]
    try:
        dat = json.loads(dat_str)
        if not isinstance(dat, list):
            return "JSON格式錯誤", 400
        ks = [o[0] for o in dat]
        mp = {o[0]: o[1] for o in dat}
    except (json.JSONDecodeError, TypeError, ValueError):
        return "JSON格式錯誤", 400

    for category in config_fields:
        for slot in category["slots"]:
            key = f"config_{category['name']}_{slot['name']}"
            if slot['type'] == "limits":
                true_keys = [k for k in ks if k.startswith(key + "_")]
                if len(true_keys) == 0:
                    return f"缺少設定項目: {key}", 400
                for true_key in true_keys:
                    val = mp[true_key]
                    str_val = f"{val[0]} per {val[1]} {val[2]}"
                    if not is_valid_limit_string(str_val):
                        return f"{str_val!r} 不是合法的速率限制", 400
            else:
                if key not in ks:
                    return f"缺少設定項目: {key}", 400
                if slot['type'] == "bool":
                    if mp[key] not in ("true", "false"):
                        return f"{mp[key]!r} 不是合法的布林值", 400
                    mp[key] = True if mp[key] == "true" else False
                elif slot['type'] == "int":
                    if not mp[key].isdigit():
                        return f"{mp[key]!r} 不是合法的整數", 400
                    mp[key] = int(mp[key])
                elif slot['type'] == "limit":
                    val = mp[key]
                    str_val = f"{val[0]} per {val[1]} {val[2]}"
                    if not is_valid_limit_string(str_val):
                        return f"{str_val!r} 不是合法的速率限制", 400

    for category in config_fields:
        cat_obj = getattr(config.config, category["name"])
        for slot in category["slots"]:
            key = f"config_{category['name']}_{slot['name']}"
            if slot['type'] == "limits":
                true_keys = [k for k in ks if k.startswith(key + "_")]
                vals = []
                for true_key in true_keys:
                    val = mp[true_key]
                    str_val = f"{val[0]} per {val[1]} {val[2]}"
                    vals.append(str_val)
                setattr(cat_obj, slot['name'], vals)
            elif slot['type'] == "limit":
                val = mp[key]
                str_val = f"{val[0]} per {val[1]} {val[2]}"
                setattr(cat_obj, slot['name'], str_val)
            else:
                setattr(cat_obj, slot['name'], mp[key])
    config.save_config()
    return "OK", 200


def stop_server():
    def stop():
        time.sleep(3)
        tools.stop_server()

    threading.Thread(target=stop, daemon=True).start()
    return "OK", 200


@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if not current_user.has(Permission.root):
        server.custom_abort(403, "需要管理員權限")
    if request.method == 'GET':
        users = datas.query(datas.User).all()
        config_fields = config.get_fields()
        return render_template("admin.html", users=users, config_fields=config_fields,
                               enumerate=enumerate)
    else:
        if request.form["action"] == "update_user":
            return update_user()
        if request.form["action"] == "parse_user":
            return jsonify(parse_user()), 200
        if request.form["action"] == "create_users":
            create_users()
            return "OK", 200
        if request.form["action"] == "update_config":
            return update_config()
        if request.form["action"] == "stop_server":
            return stop_server()
        server.custom_abort(404, "找不到指定的操作")
