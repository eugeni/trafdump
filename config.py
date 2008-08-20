#!/usr/bin/python
"""Shared configuration file for TrafDump"""

import os
import socket
import traceback
import struct
import SocketServer

LISTENPORT = 10000

COMMAND_START_CAPTURE=1
COMMAND_STOP_CAPTURE=2
COMMAND_BANDWIDTH=3

BANDWIDTH_BUFSIZE = 100 * 1000 * 1000

commands_linux = {
        "capture": "tshark -q -i %(iface)s -p -w %(output)s &",
        "stop": "killall tshark",
        "stat": "tshark -q -r %(input)s -z io,phs -z io,stat,1 > %(output)s"
        }
commands_windows = {
        "capture": "start tshark -q -i %(iface)s -p -w %(output)s",
        "stop": "taskkill /im tshark.exe",
        "stat": "tshark -q -r %(input)s -z io,phs -z io,stat,1 > %(output)s"
        }

def run_subprocess(cmd, background=True):
    """Runs a background command"""
    print "Running: %s" % cmd
    os.system("%s" % cmd)
    pass


class ReusableSocketServer(SocketServer.TCPServer):
    # TODO: allow address reuse
    allow_reuse_address = True

def connect(addr, port, timeout=None):
    """Envia mensagem por socket TCP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((addr, port))
        if timeout:
            s.settimeout(timeout)
        return s
    except:
        traceback.print_exc()
        return None

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
        id, iface = z.strip().split(".", 1)
        ifaces[iface] = id
    return ifaces
