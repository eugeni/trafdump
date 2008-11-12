#!/usr/bin/python
from reportlab.pdfgen import canvas
import time, os, sys
import glob

#find out what platform we are on and whether accelerator is
#present, in order to print this as part of benchmark info.
try:
    import _rl_accel
    ACCEL = 1
except ImportError:
    ACCEL = 0


from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4

#precalculate some basics
top_margin = A4[1] - inch
bottom_margin = inch
left_margin = inch
right_margin = A4[0] - inch
frame_width = right_margin - left_margin


def drawPageFrame(canv):
    canv.line(left_margin, top_margin, right_margin, top_margin)
    canv.setFont('Times-Italic',12)
    canv.drawString(left_margin, top_margin + 2, "TrafDump results")
    canv.line(left_margin, top_margin, right_margin, top_margin)


    canv.line(left_margin, bottom_margin, right_margin, bottom_margin)
    canv.drawCentredString(0.5*A4[0], 0.5 * inch,
               "Page %d" % canv.getPageNumber())



def run(verbose=1):

    canv = canvas.Canvas('teste.pdf', invariant=1)
    canv.setPageCompression(1)
    drawPageFrame(canv)

    #do some title page stuff
    canv.setFont("Times-Bold", 36)
    canv.drawCentredString(0.5 * A4[0], 7 * inch, "TrafDump Results")

    canv.setFont("Times-Bold", 18)
    canv.drawCentredString(0.5 * A4[0], 5 * inch, "%s" % time.asctime())

    canv.setFont("Times-Bold", 12)
    tx = canv.beginText(left_margin, 3 * inch)
    tx.textLine("Results for TrafDump execution.")
    tx.textLine("")
    tx.textLine("Performed tests:")
    tx.textLine(" - Quick Test:")
    tx.textLine("")
    tx.textLine("")
    tx.textLine("TrafDump v. 1.0")
    tx.textLine("Eugeni Dodonov, Paulo Costa, 2008")
    canv.drawText(tx)

    canv.showPage()

    drawPageFrame(canv)

    files = ["./Throughput experiment.1226455741/bandwidth.txt",
    "./multicast experiment.1226455746/multicast.txt",
    "./broadcast experiment.1226455789/broadcast.txt",
    "./multicast experiment.1226455746/multicast_800.txt",
    "./multicast experiment.1226455746/multicast_900.txt",
    "./multicast experiment.1226455746/multicast_1000.txt",
    "./broadcast experiment.1226455789/broadcast_2000.txt",
    "./broadcast experiment.1226455789/broadcast_2100.txt",
    "./broadcast experiment.1226455789/broadcast_2200.txt"]

    for z in files:
        canv.setFont('Times-Roman', 12)
        tx = canv.beginText(left_margin, top_margin - 0.5*inch)
        for line in [line.rstrip() for line in open(z).readlines() if line]:
            if len(line) > 1 and line[0] == "=":
                # temporary fix
                canv.drawImage(line[1:], 0, 0, width=640, preserveAspectRatio=True)
                canv.showPage()
                drawPageFrame(canv)
                continue
            # agora vem o texto
            tx.textLine(line.expandtabs())

            #page breaking
            y = tx.getY()   #get y coordinate
            if y < bottom_margin + 0.5*inch:
                canv.drawText(tx)
                canv.showPage()
                drawPageFrame(canv)
                canv.setFont('Times-Roman', 12)
                tx = canv.beginText(left_margin, top_margin - 0.5*inch)

                #page
                pg = canv.getPageNumber()
                if verbose and pg % 10 == 0:
                    print 'formatted page %d' % canv.getPageNumber()

        if tx:
            canv.drawText(tx)
            canv.showPage()
            drawPageFrame(canv)

    canv.save()

if __name__=='__main__':
    run()
