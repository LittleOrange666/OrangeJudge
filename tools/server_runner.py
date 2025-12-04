#!/bin/python3
import os
import signal
import subprocess
import sys
import threading
import time

main_cmd = "python3 main.py"

ask1 = """Server running:
1. kill
2. restart
3. quit
number: """

ask2 = """Server is not running:
1. start
2. quit
number: """

envs = {
    "MYSQL_DB": "orangejudge",
    "MYSQL_USER": "orangejudgeuser",
    "MYSQL_PASSWORD": "orangejudgepassword",
    "MYSQL_HOST": "localhost:3307",
    "ORANGEJUDGE_VERSION": "(dev)",
}


def main():
    process: subprocess.Popen = None

    def start():
        nonlocal process
        try:
            os.system("docker-compose -f docker-compose-nobackend.yml stop")
            time.sleep(5)
            os.system("docker-compose -f docker-compose-nobackend.yml up -d")
            time.sleep(10)
            pids = subprocess.check_output("lsof -ti :8080", shell=True).decode().split()
            for pid in pids:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                    print("Kill process", pid)
                except Exception as e:
                    print("Error while killing process:", e)
        except:
            pass
        process = subprocess.Popen(main_cmd, shell=True, preexec_fn=os.setsid, env=os.environ.copy() | envs)
    start()

    def stop():
        nonlocal process
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        process.wait()

    running = True

    def say_good_bye(signum, frame):
        print()
        print('Quiting...')
        if running:
            stop()
        print()
        sys.exit(0)

    last_restart = 0.0

    def checking():
        nonlocal last_restart, running
        while True:
            if running and process.poll() is not None:
                if time.time() - last_restart < 60:
                    running = False
                    print("Server crashed, restarting too fast, exiting...")
                    os.kill(os.getpid(), signal.SIGTERM)
                    sys.exit(0)
                print("Server crashed, restarting...")
                last_restart = time.time()
                start()
            time.sleep(3)

    signal.signal(signal.SIGINT, say_good_bye)
    signal.signal(signal.SIGTERM, say_good_bye)
    threading.Thread(target=checking, daemon=True).start()
    while True:
        if running:
            cmd = input(ask1)
            match cmd:
                case "1":
                    print("Killing...")
                    running = False
                    stop()
                case "2":
                    print("Restarting...")
                    running = False
                    stop()
                    start()
                    running = True
                case "3":
                    print("Quiting...")
                    running = False
                    stop()
                    sys.exit(0)
                case _:
                    print("Invalid command")
        else:
            cmd = input(ask2)
            match cmd:
                case "1":
                    print("Starting...")
                    start()
                    running = True
                case "2":
                    print("Quiting...")
                    sys.exit(0)
        print()


if __name__ == '__main__':
    main()
