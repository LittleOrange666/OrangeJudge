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

from flask_restx import Resource, fields

from .base import get_api_user, api_response, api, marshal_with, base_request_parser, request_parser, Form
from ..admin import update_config
from ... import objs, server, config

ns = api.namespace("admin", path="/admin", description="admin API endpoints")

config_slot = ns.model("ConfigSlot", {
    "name": fields.String(description="Configuration name"),
    "title": fields.String(description="Configuration title"),
    "type": fields.String(description="Configuration type info"),
    "value": fields.Raw(description="Configuration value"),
})

config_field = ns.model("ConfigField", {
    "name": fields.String(description="Configuration name"),
    "title": fields.String(description="Configuration title"),
    "slots": fields.List(fields.Nested(config_slot), description="Configuration slots"),
})

config_get_output = ns.model("ConfigGetOutput", {
    "config": fields.List(fields.Nested(config_field), description="Server configuration"),
})

config_save_input = request_parser(
    Form("config", type=str, required=True, help="Configuration data in JSON format")
)


@ns.route("/config")
class ServerConfig(Resource):
    @ns.doc("get_server_config")
    @ns.expect(base_request_parser)
    @marshal_with(ns, config_get_output)
    def get(self):
        """Get server configuration"""
        user = get_api_user(base_request_parser.parse_args())
        if not user.has(objs.Permission.root):
            server.custom_abort(403, "Forbidden: Root access required")
        config_fields = config.get_fields()
        return api_response({"config": config_fields})

    @ns.doc("update_server_config")
    @ns.expect(config_save_input)
    def put(self):
        """Update server configuration"""
        args = config_save_input.parse_args()
        user = get_api_user(args)
        if not user.has(objs.Permission.root):
            server.custom_abort(403, "Forbidden: Root access required")
        res, code = update_config()
        if code != 200:
            server.custom_abort(code, res)
        return api_response({
            "message": "Configuration updated successfully"
        })
