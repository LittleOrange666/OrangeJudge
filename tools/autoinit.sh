#!/bin/bash
sudo apt-get update
sudo apt-get -y install python3
sudo apt-get -y install python3-pip
sudo apt-get -y install lxc
sudo apt-get -y install lxc-templates
sudo apt-get -y install redis
sudo apt-get -y install texlive-latex-generic
sudo apt-get -y install texlive-xetex
sudo pip3 install -r tools/requirements.txt
sudo lxc-create lxc-test -t ubuntu
sudo lxc-start -n lxc-test
sudo lxc-attach -n lxc-test -- sudo apt-get update
sudo lxc-attach -n lxc-test -- sudo apt-get -y install g++
sudo lxc-attach -n lxc-test -- sudo apt-get -y install python3
sudo lxc-attach -n lxc-test -- sudo apt-get -y install pypy3
sudo lxc-attach -n lxc-test -- sudo apt-get -y install openjdk-8-jdk-headless
sudo lxc-attach -n lxc-test -- sudo apt-get -y install openjdk-17-jdk-headless
sudo lxc-attach -n lxc-test -- mkdir /judge
sudo lxc-attach -n lxc-test -- useradd judge --system --no-create-home
sudo python3 tools/file_protect.py
sudo python3 tools/add_ignored.py
echo ok > tools/inited