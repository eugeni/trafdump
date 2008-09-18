#!/usr/bin/python

import os
import glob
import sys
import re

file_re = re.compile("results.(\d+).*")
title_re = re.compile(".*: (\d+) msgs, (\d+) bandwidth")

if len(sys.argv) < 2:
    print "Uso: %s <IP>" % sys.argv[0]
    sys.exit(1)

ip = sys.argv[1]

for z in glob.glob("*%s.mcast" % ip):
    ts = file_re.findall(z)[0]
    # tenta descobrir a banda esperada
    bandwidth = 0
    try:
        line = open("results.%s.txt" % ts).readline()
        msgs, band = title_re.findall(line)[0]
        band = int(band)
    except:
        pass
    data = open(z).readlines()[2:-1]
    # valores
    vals = [float(x.split(" ")[1]) for x in data]
    # media
    x = reduce(lambda x, y: x+y, vals) / len(vals)

    foundband = ((1/x) * 8 * 1450) / 1024

    print "lat: %f, bandwidth: %f kbps, max. bandwidth: %d kbps" % (x, foundband, band)
