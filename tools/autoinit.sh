#!/bin/bash
sudo apt-get update
sudo apt-get -y install python3
sudo apt-get -y install python3-pip
sudo apt-get -y install redis
sudo apt-get -y install texlive-latex-generic
sudo apt-get -y install texlive-xetex
sudo pip3 install -r tools/requirements.txt
sudo tools/prepare_lxc.sh
sudo tools/prepare_judger.sh
sudo python3 tools/file_protect.py
sudo python3 tools/add_ignored.py
echo ok > tools/inited