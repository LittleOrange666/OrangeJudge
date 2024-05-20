#!/bin/bash
if [[ -f 'tools/inited' ]]; then
  echo "OK"
else
  chmod +x ./tools/autoinit.sh
  sudo ./tools/autoinit.sh
fi
sudo python3 main.py