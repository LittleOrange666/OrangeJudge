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

import os
import subprocess
import sys
import traceback

from gunicorn.app.base import BaseApplication

from modules import contests, constants, datas, executing, locks, login, problemsetting, server, tasks, tools, config, \
    judge
import modules.routers


class StandaloneApplication(BaseApplication):

    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self):
        config_data = {key: value for key, value in self.options.items()
                       if key in self.cfg.settings and value is not None}
        for key, value in config_data.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application


def main():
    if not sys.platform.startswith("linux"):
        raise RuntimeError("The judge server only supports Linux")
    try:
        judge.init()
        executing.init()
        constants.init()
        # following do nothing
        config.init()
        locks.init()
        tools.init()
        modules.routers.init()
        redis_host = os.environ.get("REDIS_HOST", "localhost")
        if not server.check_port(redis_host, 6379):
            subprocess.Popen("redis-server")
        with server.app.app_context():  # following need sqlalchemy
            datas.init()
            login.init()
            tasks.init()
            contests.init()
            problemsetting.init()
    except Exception as e:
        print("Error while initializing:", e)
        traceback.print_exception(e)
        return
    options = {
        'bind': '%s:%s' % ('[::]', str(config.server.port)),
        'workers': config.server.workers,
        'timeout': config.server.timeout,
    }
    StandaloneApplication(server.app, options).run()


if __name__ == '__main__':
    main()
