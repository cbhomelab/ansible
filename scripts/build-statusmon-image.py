#!/usr/bin/env python3
"""Customise a Raspberry Pi OS Lite (trixie, cloud-init) image: hostname, key-only SSH user. No root needed."""
import subprocess, sys, os, warnings
warnings.filterwarnings("ignore")
from pyfatfs.PyFatFS import PyFatFS
SRC, OUT = sys.argv[1], sys.argv[2]
KEYS = [open(os.path.expanduser(p)).read().strip() for p in sys.argv[3:]]
START, COUNT = 16384, 1048576   # boot partition, sectors (verified with sfdisk -d)
HOST, USER = "statusmon", "statusmon"
user_data = f"""#cloud-config
hostname: {HOST}
manage_etc_hosts: true
timezone: America/Los_Angeles
ssh_pwauth: false
users:
- name: {USER}
  gecos: Status monitor
  groups: [sudo, video, input, gpio, i2c, spi, adm]
  shell: /bin/bash
  lock_passwd: true
  sudo: ALL=(ALL) NOPASSWD:ALL
  ssh_authorized_keys:
""" + "".join(f"  - {k}\n" for k in KEYS) + """enable_ssh: true
runcmd:
- [ systemctl, enable, --now, ssh ]
"""
network = """network:
  version: 2
  ethernets:
    eth0:
      dhcp4: true
      optional: false
"""
subprocess.run(["cp", "--reflink=auto", SRC, OUT], check=True)
subprocess.run(["dd", f"if={OUT}", "of=boot.fat", "bs=512", f"skip={START}", f"count={COUNT}", "status=none"], check=True)
f = PyFatFS("boot.fat")
for n,c in (("/user-data",user_data),("/network-config",network)):
    f.remove(n)
    f.writetext(n,c)
f.close()
subprocess.run(["dd", "if=boot.fat", f"of={OUT}", "bs=512", f"seek={START}", "conv=notrunc", "status=none"], check=True)
os.remove("boot.fat")
print("built", OUT)
