#!/bin/bash
cd /python
tar zxvf Python-3.6.9.tgz
rm Python-3.6.9.tgz
cd Python-3.6.9
./configure --prefix=/python/python3.6.9
make
sudo make install
cd /python
rm -rf Python-3.6.9
tar zxvf Python-3.10.14.tgz
rm Python-3.10.14.tgz
cd Python-3.10.14
./configure --prefix=/python/python3.10.14
make
sudo make install
cd /python
rm -rf Python-3.10.14
tar jxvf pypy3.6-v7.3.2-linux64.tar.bz2
rm pypy3.6-v7.3.2-linux64.tar.bz2
mv pypy3.6-v7.3.2-linux64 pypy3.6.9
tar jxvf pypy3.10-v7.3.16-linux64.tar.bz2
rm pypy3.10-v7.3.16-linux64.tar.bz2
mv pypy3.10-v7.3.16-linux64 pypy3.10.14
rm install_python.sh