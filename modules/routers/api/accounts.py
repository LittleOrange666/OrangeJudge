"""
OrangeJudge, a competitive programming platform

Copyright (C) 2024-2025 LittleOrange666 (orangeminecraft123@gmail.com)

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
import random
import time

from flask_login import login_user, current_user
from flask_restx import Resource, fields

from .base import get_api_user, api_response, api, marshal_with, request_parser, Form, base_request_parser
from ... import datas, objs, server, constants, login, config, locks

ns = api.namespace("accounts", path="/accounts", description="Accounts related API endpoints")

# Shared verification code logic
# This assumes that locks.manager is a singleton across the application
verify_codes = locks.manager.dict()


def use_code(email: str, verify: str) -> bool:
    if email not in verify_codes:
        return False
    dat = verify_codes[email]
    if dat[1] < time.time() - 600:
        del verify_codes[email]
        return False
    if dat[0] != verify[:6]:
        return False
    del verify_codes[email]
    return True


# region Models
login_status_output = ns.model("LoginStatusOutput", {
    "logged_in": fields.Boolean(description="Whether the user is logged in"),
    "username": fields.String(description="Username of the logged-in user", required=False),
    "display_name": fields.String(description="Display name of the logged-in user", required=False),
})

signup_output = ns.model("SignupOutput", {
    "message": fields.String(description="Status message")
})

settings_output = ns.model("SettingsOutput", {
    "display_name": fields.String,
    "email": fields.String,
    "username": fields.String,
    "permissions": fields.List(fields.String)
})

gen_key_output = ns.model("GenKeyOutput", {
    "api_key": fields.String(description="The new API key")
})

user_info_output = ns.model("UserInfoOutput", {
    "username": fields.String,
    "display_name": fields.String,
})
# endregion

# region Parsers
login_user_input = request_parser(
    Form("username", "Username for authentication", type=str, required=True),
    Form("password", "Password for authentication", type=str, required=True)
)

signup_input = request_parser(
    Form("email", "Email address", type=str, required=True),
    Form("user_id", "Username", type=str, required=True),
    Form("password", "Password (at least 6 characters)", type=str, required=True),
    Form("password_again", "Repeat password", type=str, required=True),
    Form("verify", "Email verification code", type=str, required=False)
)

get_code_input = request_parser(
    Form("email", "Email address to send code to", type=str, required=True)
)

profile_update_input = request_parser(
    Form("display_name", "New display name", type=str, required=True)
)

password_change_input = request_parser(
    Form("old_password", "Current password", type=str, required=True),
    Form("new_password", "New password (at least 6 characters)", type=str, required=True)
)

forget_password_input = request_parser(
    Form("email", "Your email address", type=str, required=True),
    Form("verify", "Email verification code", type=str, required=True),
    Form("password", "New password", type=str, required=True)
)
# endregion


@ns.route("/signup")
class Signup(Resource):
    @ns.doc("create_account")
    @ns.expect(signup_input)
    @marshal_with(ns, signup_output)
    def post(self):
        """Create a new user account."""
        if not config.account.signup:
            server.custom_abort(503, "Signup is disabled.")
        args = signup_input.parse_args()
        need_verify = config.smtp.enabled
        email = args["email"]
        user_id = args["user_id"]
        password = args["password"]
        password_again = args["password_again"]
        verify = args.get("verify") if need_verify else ""

        if constants.user_id_reg.match(user_id) is None:
            server.custom_abort(400, "Invalid user ID format.")
        if login.exist(user_id):
            server.custom_abort(409, "User ID is already taken.")
        if datas.count(datas.User, email=email) > 0:
            server.custom_abort(409, "Email is already in use.")
        if len(password) < 6:
            server.custom_abort(400, "Password must be at least 6 characters long.")
        if password != password_again:
            server.custom_abort(400, "Passwords do not match.")
        if need_verify and not use_code(email, verify):
            server.custom_abort(400, "Invalid verification code.")

        login.create_account(email, user_id, password)
        with datas.SessionContext():
            user, msg = login.try_login(user_id, password)
            if user is None:
                server.custom_abort(500, f"Registration failed: {msg}")
            login_user(user)
        return api_response({"message": "OK"})


@ns.route("/get_code")
class GetCode(Resource):
    @ns.doc("get_verification_code")
    @ns.expect(get_code_input)
    @server.limiter.limit(config.smtp.limit, override_defaults=False)
    def post(self):
        """Send an email verification code."""
        if not config.smtp.enabled:
            server.custom_abort(503, "Email service is not enabled.")
        args = get_code_input.parse_args()
        email = args["email"]
        if constants.email_reg.match(email) is None:
            server.custom_abort(400, "Invalid email format.")
        if email in verify_codes and verify_codes[email][1] > time.time() - 60:
            server.custom_abort(429, "Please wait before requesting a new code.")

        idx = "".join(str(random.randint(0, 9)) for _ in range(6))
        verify_codes[email] = (idx, time.time())

        if not login.send_code(email, idx):
            server.custom_abort(503, "Failed to send verification email.")
        return api_response({"message": "OK"})


@ns.route("/settings")
class Settings(Resource):
    @ns.doc("get_user_settings")
    @ns.expect(base_request_parser)
    @marshal_with(ns, settings_output)
    def get(self):
        """Get current user's settings."""
        user = get_api_user(base_request_parser.parse_args())
        data: datas.User = user.data
        perms = [perm.name for perm in objs.Permission if user.has(perm) and
                 perm not in (objs.Permission.admin, objs.Permission.root)]
        return api_response({
            "display_name": data.display_name,
            "email": data.email,
            "username": user.id,
            "permissions": perms
        })


@ns.route("/settings/profile")
class SettingsProfile(Resource):
    @ns.doc("update_user_profile")
    @ns.expect(profile_update_input)
    def put(self):
        """Update user's profile information."""
        args = profile_update_input.parse_args()
        user = get_api_user(args)
        display_name = args["display_name"]
        if len(display_name) > 120 or len(display_name) < 1:
            server.custom_abort(400, "Display name must be between 1 and 120 characters.")
        data: datas.User = user.data
        data.display_name = display_name
        user.save()
        return api_response({"message": "Profile updated."})


@ns.route("/settings/password")
class SettingsPassword(Resource):
    @ns.doc("change_user_password")
    @ns.expect(password_change_input)
    def put(self):
        """Change user's password."""
        args = password_change_input.parse_args()
        user = get_api_user(args)
        old_password = args["old_password"]
        new_password = args["new_password"]
        data: datas.User = user.data

        if login.try_hash(old_password) != data.password_sha256_hex:
            server.custom_abort(403, "Incorrect old password.")
        if len(new_password) < 6:
            server.custom_abort(400, "New password must be at least 6 characters long.")

        data.password_sha256_hex = login.try_hash(new_password)
        user.save()
        return api_response({"message": "Password changed."})


@ns.route("/gen_key")
class GenKey(Resource):
    @ns.doc("generate_api_key")
    @ns.expect(base_request_parser)
    @marshal_with(ns, gen_key_output)
    def post(self):
        """Generate a new API key. The old key will be invalidated."""
        user = get_api_user(base_request_parser.parse_args())
        data: datas.User = user.data
        key = login.gen_key()
        data.api_key = login.try_hash(key)
        user.save()
        return api_response({"api_key": key})


@ns.route("/forget_password")
class ForgetPassword(Resource):
    @ns.doc("reset_password")
    @ns.expect(forget_password_input)
    def post(self):
        """Reset password using email verification."""
        if not config.smtp.enabled:
            server.custom_abort(503, "Email service is not enabled.")

        if current_user.is_authenticated:
            server.custom_abort(400, "You are already logged in.")

        args = forget_password_input.parse_args()
        email = args["email"]
        verify = args["verify"]
        password = args["password"]

        user = login.get_user(email)
        if user is None:
            server.custom_abort(404, "User with this email not found.")
        if not use_code(email, verify):
            server.custom_abort(403, "Invalid verification code.")

        data = user.data
        data.password_sha256_hex = login.try_hash(password)
        user.save()
        return api_response({"message": "Password has been reset."})


@ns.route("/user/<string:username>")
class UserInfo(Resource):
    @ns.doc("get_user_public_info")
    @marshal_with(ns, user_info_output)
    def get(self, username):
        """Get public information about a user."""
        username = username.lower()
        user = login.get_user(username)
        if user is None:
            server.custom_abort(404, "User not found.")
        user_data = user.data
        return api_response({
            "username": username,
            "display_name": user_data.display_name
        })
