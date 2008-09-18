#!/usr/bin/python
# encoding: utf-8

import os
import sys
import re
import glob

from pylab import *

import gettext
import __builtin__
__builtin__._ = gettext.gettext

def analyze_bandwidth(timestamp, clients):
    """Avalia a banda dos clientes"""
    xtitles = []
    bandwidth = []
    for client in clients:
        data = open("results.%s.%s.band" % (timestamp, client)).readlines()
        upload = float(data[1].split(" ")[3]) / 1000000
        download = float(data[2].split(" ")[3]) / 1000000
        bandwidth.append(upload)
        xtitles.append(_("\n          Upload"))
        bandwidth.append(download)
        xtitles.append(_("          Download\n%s") % client)
    fig = figure()
    title(_("Bandwidth evaluation for %d clients" % len(clients)))
    bar(range(len(bandwidth)), bandwidth)
    xticks(arange(len(xtitles)), xtitles)
    ylabel(_("Bandwidth (MB/s)"))
    grid()
    show()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "Usage: %s <experiment timestamp>" % sys.argv[0]
        sys.exit(1)
    timestamp = sys.argv[1]

    print timestamp

    # process the files
    clients_r = re.compile('results.\d+.(\d+\.\d+\.\d+\.\d+).(\w+)')
    files = glob.glob("results.%s.*" % timestamp)
    res = clients_r.findall("\n".join(files))
    if not res:
        # no files found
        sys.exit(0)
    experiments = {}
    for client, type in res:
        if type not in experiments:
            experiments[type] = [client]
        else:
            experiments[type].append(client)
    # agora calcula os resultados
    for exp in experiments:
        if exp == "band":
            analyze_bandwidth(timestamp, experiments[exp])
        elif exp == "mcast":
            analyze_mcast(timestamp, experiments[exp])
        elif exp == "bcast":
            analyze_bcast(timestamp, experiments[exp])
        else:
            print "Unknown experiment %s" % exp

