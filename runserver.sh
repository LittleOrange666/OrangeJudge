#!/bin/bash
if [[ -f 'tools/inited' ]]; then
  echo "OK"
else
  sudo ./tools/autoinit.sh
fi
sudo python3 server.py
pause