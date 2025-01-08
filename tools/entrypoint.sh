#!/bin/sh
chown -R 1500:1500 /app/sandbox
chown -R 1500:1500 /app/data
USER_NAME="orangejudge"
exec gosu $USER_NAME python3 main.py