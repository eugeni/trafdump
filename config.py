#!/usr/bin/python
"""Shared configuration file for TrafDump"""

import os

commands_linux = {
        "capture": "tshark -q -i %(iface)d -p -w %(output)s",
        "stop": "killall tshark",
        "stat": "tshark -q -r %(input)s -z io,phs -z io,stat,1 > %(output)s"
        }
commands_windows = {
        "capture": "tshark -q -i %(iface)s -p -w %(output)s",
        "stop": "taskkill /im tshark.exe",
        "stat": "tshark -q -r %(input)s -z io,phs -z io,stat,1 > %(output)s"
        }

def get_os():
    """Returns the name of the OS"""
    try:
        # quick workaround - windows has no 'uname' :)
        ret = os.uname()
        return "Linux"
    except:
        return "Windows"

def list_ifaces():
    """Returns a list of network interfaces"""
    list = os.popen("tshark -D").readlines()
    ifaces = {}
    for z in list:
        id, iface = z.strip().split(".")
        ifaces[iface] = id
    return ifaces
