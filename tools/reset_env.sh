#!/bin/bash
sudo lxc-stop -n lxc-test
sudo lxc-destroy -n lxc-test
sudo ./autoinit.sh