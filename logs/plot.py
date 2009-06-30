#!/usr/bin/python

from pylab import *
import sys
import glob

files = glob.glob("*.dat")
for z in files:
    data = open(z).readlines()
    band_exp = [int(x.strip().replace("  ", " ").split(" ")[0]) for x in data if len(x) > 1]
    real_band = [float(x.strip().replace("  ", " ").split(" ")[4]) for x in data if len(x) > 1]

    figure(figsize=(len(band_exp), 8))
    exp = z.replace(".dat", "")
    title(exp)
    plot(band_exp, label='Expected bandwidth')
    plot(real_band, label='Real bandwidth')
    xticks(range(len(band_exp)), band_exp)
    ylabel("Bandwidth (Kbps)")
    xlabel("Expected bandwidth (Kbps)")
    grid()
    legend()
    savefig("%s.png" % exp, format="png")
    #show()
