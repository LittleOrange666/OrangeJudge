#!/bin/bash
sudo apt-get -y install wget
sudo apt-get -y install lxc
sudo apt-get -y install lxc-templates
sudo lxc-create lxc-test -t ubuntu
sudo lxc-start -n lxc-test
sudo lxc-attach -n lxc-test -- sudo apt-get update
sudo lxc-attach -n lxc-test -- sudo apt-get -y install gcc
sudo lxc-attach -n lxc-test -- sudo apt-get -y install g++
sudo lxc-attach -n lxc-test -- sudo apt-get -y install bzip2
sudo lxc-attach -n lxc-test -- sudo apt-get -y install make
sudo lxc-attach -n lxc-test -- sudo apt-get -y install openjdk-8-jdk-headless
sudo lxc-attach -n lxc-test -- sudo apt-get -y install openjdk-17-jdk-headless
wget https://www.python.org/ftp/python/3.6.9/Python-3.6.9.tgz
wget https://www.python.org/ftp/python/3.10.14/Python-3.10.14.tgz
wget https://downloads.python.org/pypy/pypy3.6-v7.3.2-linux64.tar.bz2
wget https://downloads.python.org/pypy/pypy3.10-v7.3.16-linux64.tar.bz2
sudo lxc-attach -n lxc-test -- mkdir /python
sudo mv Python-3.6.9.tgz /var/lib/lxc/lxc-test/rootfs/python
sudo mv Python-3.10.14.tgz /var/lib/lxc/lxc-test/rootfs/python
sudo mv pypy3.6-v7.3.2-linux64.tar.bz2 /var/lib/lxc/lxc-test/rootfs/python
sudo mv pypy3.10-v7.3.16-linux64.tar.bz2 /var/lib/lxc/lxc-test/rootfs/python
sudo cp tools/install_python.sh /var/lib/lxc/lxc-test/rootfs/python
sudo lxc-attach -n lxc-test -- sudo chmod +x /python/install_python.sh
sudo lxc-attach -n lxc-test -- sudo /python/install_python.sh
sudo lxc-attach -n lxc-test -- mkdir /judge
sudo lxc-attach -n lxc-test -- useradd judge --system --no-create-home