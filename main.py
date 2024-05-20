import sys

from modules import executing, problemsetting, constants, tasks, server


def main():
    if not sys.platform.startswith("linux"):
        raise RuntimeError("The judge server only supports Linux")
    if not executing.call(["whoami"])[0].startswith("root\n"):
        raise RuntimeError("The judge server must be run as root")
    problemsetting.system(f"sudo lxc-start {constants.lxc_name}")
    problemsetting.system(f"sudo cp -r -f judge /var/lib/lxc/{constants.lxc_name}/rootfs/")
    executing.init()
    tasks.init()
    problemsetting.init()
    server.app.run("0.0.0.0", port=8898)


if __name__ == '__main__':
    main()