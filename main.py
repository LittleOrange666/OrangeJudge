import sys

from modules import contests, constants, data, executing, locks, login, problemsetting, server, tasks, tools
import modules.routers


def main():
    if not sys.platform.startswith("linux"):
        raise RuntimeError("The judge server only supports Linux")
    if not executing.call(["whoami"])[0].startswith("root\n"):
        raise RuntimeError("The judge server must be run as root")
    tools.system(f"sudo lxc-start {constants.lxc_name}")
    tools.system(f"sudo cp -r -f judge /var/lib/lxc/{constants.lxc_name}/rootfs/")
    with server.app.app_context():
        contests.init()
        data.init()
        executing.init()
        locks.init()
        login.init()
        tasks.init()
        problemsetting.init()
        tools.init()
        modules.routers.init()
    server.app.run("0.0.0.0", port=8898)


if __name__ == '__main__':
    main()
