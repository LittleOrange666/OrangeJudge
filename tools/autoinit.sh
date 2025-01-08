#!/bin/bash
sudo apt-get update
sudo apt-get -y install python3
sudo apt-get -y install python3-pip
sudo apt-get -y install redis
sudo apt-get -y install texlive-latex-generic
sudo apt-get -y install texlive-xetex
sudo apt-get -y install docker
sudo apt-get -y install docker-compose
sudo pip3 install -r tools/requirements.txt
sudo python3 tools/add_ignored.py
echo ok > tools/inited