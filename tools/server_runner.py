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


def main():
    process = subprocess.Popen(main_cmd, shell=True, preexec_fn=os.setsid)

    def start():
        nonlocal process
        process = subprocess.Popen(main_cmd, shell=True, preexec_fn=os.setsid)

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
