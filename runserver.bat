IF EXIST tools/inited () ELSE (wsl -e sudo tools/autoinit.sh)
wsl -e sudo python3 server.py
pause