import os
import subprocess

base = "boot dev etc home media mnt opt root run srv tmp var sbin lib32 libx32".split()
for s in base:
    os.system("sudo lxc-attach -n lxc-test -- chmod 700 -R /"+s)
keys = "python pypy cat java javac".split()
usr = "games include lib32 libexec libx32 local sbin share src".split()
for s in usr:
    os.system("sudo lxc-attach -n lxc-test -- chmod 700 -R /usr/"+s)
ns = subprocess.run("sudo lxc-attach -n lxc-test -- ls /usr/bin", shell=True, capture_output=True).stdout.decode().split()
for n in ns:
    if not any(map(n.__contains__, keys)):
        os.system("sudo lxc-attach -n lxc-test -- chmod 700 /usr/bin/"+n)
os.system("sudo lxc-attach -n lxc-test -- chmod 755 /usr/bin")
