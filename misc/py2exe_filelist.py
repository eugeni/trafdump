#!/usr/bin/python

import os
from distutils.filelist import findall

dirs = os.popen("find distfiles -type d").readlines()

print "distfiles = [ \\"
for dir in dirs[1:]:
    dir = dir.strip()
    outdir = dir.replace("distfiles/", "")
    files = ["\"%s\"" % x.strip() for x in os.popen("find %s -maxdepth 1 -type f" % dir).readlines()]
    print "\t(\"%s\", [ %s ])," % (outdir, ", ".join(files))
print "]"
