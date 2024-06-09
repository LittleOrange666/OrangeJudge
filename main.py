import sys
from gunicorn.app.base import BaseApplication

from modules import contests, constants, datas, executing, locks, login, problemsetting, server, tasks, tools, config
import modules.routers


class StandaloneApplication(BaseApplication):

    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self):
        config = {key: value for key, value in self.options.items()
                  if key in self.cfg.settings and value is not None}
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application


def main():
    if not sys.platform.startswith("linux"):
        raise RuntimeError("The judge server only supports Linux")
    if not executing.call(["whoami"])[0].startswith("root\n"):
        raise RuntimeError("The judge server must be run as root")
    tools.system(f"sudo lxc-start {constants.lxc_name}")
    tools.system(f"sudo cp -r -f judge /var/lib/lxc/{constants.lxc_name}/rootfs/")
    with server.app.app_context():
        config.init()
        locks.init()
        tools.init()
        datas.init()
        login.init()
        executing.init()
        tasks.init()
        contests.init()
        problemsetting.init()
        modules.routers.init()
    options = {
        'bind': '%s:%s' % ('0.0.0.0', str(config.get("server.port"))),
        'workers': config.get("server.workers"),
        'timeout': config.get("server.timeout"),
    }
    StandaloneApplication(server.app, options).run()
    # server.app.run("0.0.0.0", port=config.get("server.port"))


if __name__ == '__main__':
    main()
