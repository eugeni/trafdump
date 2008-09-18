#!/bin/sh
#
# Creates a binary pack for current version.
#

REVNO=$(bzr revno)

COMPRESS="-t7z -m0=BCJ2 -m1=LZMA:d=25:fb=255:a=2:lc=7:mf=bt3 -m2=LZMA:d=19:fb=128:a=2:lc=0:lp=2:mf=bt3 -m3=LZMA:d=19:fb=128:a=2:lc=0:lp=2:mf=bt3 -mb0:1 -mb0s1:2 -mb0s2:3"

echo $REVNO

for z in client trafdump; do
	7z a ${z}-v${REVNO}.7z ${COMPRESS} $z
	zip -r9 ${z}-v${REVNO}.zip $z
done
