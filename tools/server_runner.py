import os
import signal
import subprocess
import sys

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

    signal.signal(signal.SIGINT, say_good_bye)
    signal.signal(signal.SIGTERM, say_good_bye)
    while True:
        if running:
            cmd = input(ask1)
            match cmd:
                case "1":
                    print("Killing...")
                    stop()
                    running = False
                case "2":
                    print("Restarting...")
                    stop()
                    start()
                case "3":
                    print("Quiting...")
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
