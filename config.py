#!/usr/bin/python
"""Shared configuration file for TrafDump"""

import os
import time
import socket
import traceback
import struct
import SocketServer

LISTENPORT = 10000
MCASTPORT = 10001
BCASTPORT = 10002

MCASTADDR="224.51.105.104"
BCASTADDR="255.255.255.255"

COMMAND_START_CAPTURE=1
COMMAND_STOP_CAPTURE=2
COMMAND_BANDWIDTH_TCP=3
COMMAND_BANDWIDTH_BROADCAST_START=4
COMMAND_BANDWIDTH_BROADCAST_STOP=5
COMMAND_BANDWIDTH_MULTICAST_START=6
COMMAND_BANDWIDTH_MULTICAST_STOP=7

BANDWIDTH_BUFSIZE = 10 * 1000 * 1000
DATAGRAM_SIZE=1400

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

def connect(addr, port, timeout=None, retries=5):
    """Envia mensagem por socket TCP"""
    for z in range(retries):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((addr, port))
            if timeout:
                s.settimeout(timeout)
            return s
        except:
            traceback.print_exc()
            print "Attempting again (%d of %d).." % (z+1, retries)
            time.sleep(1)
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

def timefunc():
    """Detects the most apropriate time function"""
    if get_os() == "Windows":
        return time.clock
    else:
        return time.time

# socket functions
def sock_mcast():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_IP)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    return s

def sock_bcast():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_IP)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    return s

