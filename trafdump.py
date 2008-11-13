#!/usr/bin/python
"""
Teacher GUI using GLADE
"""

# TODO: detectar quando conexoes nao sao estabelecidas
# TODO: tirar redundancias entre multicast e broadcast

import sys
import traceback
import time

import socket
import struct

import os
import logging
import gtk
import gtk.glade
import pygtk
import gobject

import Queue
import SocketServer
import socket
from threading import Thread

import glob
import re

# drawing
import matplotlib
matplotlib.use("gdk")
from matplotlib.backends.backend_gtk import FigureCanvasGTK as FigureCanvas
from matplotlib.backends.backend_gtk import NavigationToolbar2GTK as NavigationToolbar
from pylab import *

# report generation
from reportlab.pdfgen import canvas
try:
    import _rl_accel
    ACCEL = 1
except ImportError:
    ACCEL = 0
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4

# localization
import gettext
import __builtin__
__builtin__._ = gettext.gettext

from config import *

MACHINES_X = 7
MACHINES_Y = 37
STEP_X = 80
STEP_Y = 65

# helper functions

def printts(ts):
    return time.asctime(time.localtime(int(ts)))

# regexps
res_r = re.compile('results.(\d+).txt')
clients_r = re.compile('results.\d+.(\d+\.\d+\.\d+\.\d+).(\w+)')

def find_clients(timestamp):
    """Finds clients for experiment"""
    files = glob.glob("results.%s.*" % timestamp)
    res = clients_r.findall("\n".join(files))
    if not res:
        print "No clients found!"
    clients = []
    exp = None
    for client, type in res:
        exp = type
        if client in clients:
            continue
        clients.append(client)
    return (exp, clients)

class ReportWriter:
    """Generates the final report"""
    def __init__(self):
        self.top_margin = A4[1] - inch
        self.bottom_margin = inch
        self.left_margin = inch
        self.right_margin = A4[0] - inch
        self.frame_width = self.right_margin - self.left_margin

    def drawPageFrame(self, canv):
        canv.line(self.left_margin, self.top_margin, self.right_margin, self.top_margin)
        canv.setFont('Times-Italic',12)
        canv.drawString(self.left_margin, self.top_margin + 2, "TrafDump results")
        canv.line(self.left_margin, self.top_margin, self.right_margin, self.top_margin)

        canv.line(self.left_margin, self.bottom_margin, self.right_margin, self.bottom_margin)
        canv.drawCentredString(0.5*A4[0], 0.5 * inch,
                   "Page %d" % canv.getPageNumber())

    def report(self, dirname, files):
        """Generates the report"""
        canv = canvas.Canvas("%s/results.pdf" % dirname, invariant=1)
        canv.setPageCompression(1)
        self.drawPageFrame(canv)

        #do some title page stuff
        canv.setFont("Times-Bold", 36)
        canv.drawCentredString(0.5 * A4[0], 7 * inch, "TrafDump Results")

        canv.setFont("Times-Bold", 18)
        canv.drawCentredString(0.5 * A4[0], 5 * inch, "%s" % time.asctime())

        canv.setFont("Times-Bold", 12)
        tx = canv.beginText(self.left_margin, 3 * inch)
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

        self.drawPageFrame(canv)

        print files
        for z in files:
            print z
            canv.setFont('Times-Roman', 12)
            tx = canv.beginText(self.left_margin, self.top_margin - 0.5*inch)
            for line in [line.rstrip() for line in open(z).readlines() if line]:
                if len(line) > 1 and line[0] == "=":
                    # temporary fix
                    canv.drawImage(line[1:], 0, 0, width=640, preserveAspectRatio=True)
                    canv.showPage()
                    self.drawPageFrame(canv)
                    continue
                # agora vem o texto
                tx.textLine(line.expandtabs())

                #page breaking
                y = tx.getY()   #get y coordinate
                if y < self.bottom_margin + 0.5*inch:
                    canv.drawText(tx)
                    canv.showPage()
                    self.drawPageFrame(canv)
                    canv.setFont('Times-Roman', 12)
                    tx = canv.beginText(self.left_margin, self.top_margin - 0.5*inch)
            if tx:
                canv.drawText(tx)
                canv.showPage()
                self.drawPageFrame(canv)

        canv.save()


# {{{ TrafdumpRunner
class TrafdumpRunner(Thread):
    selected_machines = 0
    """TrafDump service"""
    def __init__(self, gui):
        """Initializes the benchmarking thread"""
        Thread.__init__(self)

        # GUI
        self.gui = gui
        self.gui.set_service(self)

        # connected machines
        self.machines = []

        # inicializa o timestamp
        self.curtimestamp = 0

        # report writer
        self.report_writer = ReportWriter()

        # experiments queue
        self.experiments = Queue.Queue()

    def bandwidth(self, dirname, machines):
        """Inicia a captura"""
        print "Captura iniciada"
        self.gui.start_bandwidth()
        for z in machines:
            print "Enviando para %s" % z
            self.gui.show_progress(_("TCP Bandwidth test for %s") % z)
            # enviando mensagem para cliente para iniciar a captura
            s = connect(z, LISTENPORT, timeout=5)
            if not s:
                print _("Erro conectando a %s!" % z)
                traceback.print_exc()
                # Marca a maquina como offline
                self.gui.set_offline(z)

            # envia a mensagem
            try:
                s.send(struct.pack("<b", COMMAND_BANDWIDTH_TCP))
                # envia o timestamp do experimento e a descricao
                self.gui.show_progress(_("TCP Bandwidth test for %s: upload") % z)
                t1 = timefunc()
                tosend = BANDWIDTH_BUFSIZE
                # temporary packet
                packet = " " * 65536
                while tosend > 0:
                    if tosend > 65536:
                        sendl = 65536
                    else:
                        sendl = tosend
                    count = s.send(packet[:sendl])
                    tosend -= count
                t2 = timefunc()
                time_up = t2 - t1
                bandwidth_up = float(BANDWIDTH_BUFSIZE / time_up)
                print "Upload bandwidth: %f Bytes/sec in %f sec, %f MB/sec" % (bandwidth_up, time_up, (bandwidth_up / 1000000))
                self.gui.show_progress(_("TCP Bandwidth test for %s: download") % z)
                t3 = timefunc()
                torecv = BANDWIDTH_BUFSIZE
                # temporary packet
                while torecv > 0:
                    data = s.recv(65536)
                    if not data:
                        print "Error: no data received!"
                        return
                    torecv -= len(data)
                t4 = timefunc()
                s.close()
                time_down = t4 - t3
                bandwidth_down = float(BANDWIDTH_BUFSIZE / time_down)
                print "Download bandwidth: %f Bytes/sec in %f sec, %f MB/sec" % (bandwidth_down, time_down, (bandwidth_down / 1000000))
                print "Saving results to %s/%s.band" % (dirname, z)
                fd = open("%s/%s.band" % (dirname, z), "w")
                fd.write("Buffer size: %d\nUpload: %f sec, %f bytes/sec\nDownload: %f sec, %f bytes/sec\n" % (BANDWIDTH_BUFSIZE, time_up, bandwidth_up, time_down, bandwidth_down))
                fd.close()
            except:
                print _("Erro enviando mensagem para %s: %s" % (z, sys.exc_value))
                traceback.print_exc()
                # Marca a maquina como offline
                self.gui.set_offline(z)
            self.gui.show_progress(_("TCP Bandwidth test for %s finished") % z)
        # Agora analisa os resultados
        self.gui.show_progress(_("Analyzing overall TCP bandwidth.."))
        self.analyze_bandwidth(dirname, machines)

    def analyze_bandwidth(self, dirname, clients):
        """Avalia a banda dos clientes"""
        # Resulting pdf lines
        lines = []
        xtitles = []
        uploads = []
        downloads = []
        bandwidth = []

        # gerar o cabecalho
        lines.append(_("TCP Bandwidth Evaluation"))
        lines.append(_("Experiment: %s") % dirname)
        lines.append(_("Clients: %s\n") % (",".join(clients)))

        for client in clients:
            lastip = client.split(".")[-1]
            data = open("%s/%s.band" % (dirname, client)).readlines()
            upload = float(data[1].split(" ")[3]) / 1000000
            download = float(data[2].split(" ")[3]) / 1000000
            uploads.append(upload)
            downloads.append(download)

            # grafico
            xtitles.append(_("%s\nUp") % lastip)
            xtitles.append(_("%s\nDown") % lastip)
            bandwidth.append(upload)
            bandwidth.append(download)

        # generates CSV file
        output = open("%s/bandwidth.csv" % dirname, "w")
        print >>output, _("Client, upload, download")
        if uploads:
            meanupload = reduce(lambda x, y: x + y, uploads) / len(uploads)
        else:
            meanupload = 0
        if downloads:
            meandownload = reduce(lambda x, y: x + y, downloads) / len(downloads)
        else:
            meandownload = 0
        print >>output, _("All clients, %f, %f") % (meanupload, meandownload)
        lines.append(_("All clients:\n\tAverage upload: %f MB/sec\n\tAverage download: %f MB/sec") % (meanupload, meandownload))
        for z in range(len(clients)):
            client = clients[z]
            upload = uploads[z]
            download = downloads[z]
            print >>output, "%s, %f, %f" % (client, upload, download)
            lines.append(_("%s:\n\tUpload: %f MB/sec\n\tDownload: %f MB/sec") % (client, upload, download))
        output.close()

        # generates figures
        if len(clients) > 1:
            fig = figure(figsize=(len(clients) * 3, 12))
        else:
            fig = figure()

        ax = fig.add_subplot(111)
        if len(clients) == 1:
            fig.suptitle(_("Bandwidth evaluation for %s" % clients[0]))
        else:
            fig.suptitle(_("Bandwidth evaluation for %d clients" % len(clients)))
        ax.bar(range(len(bandwidth)), bandwidth)
        xticks(arange(len(xtitles)), xtitles)
        ylabel(_("Bandwidth (MB/s)"))
        ax.grid()
        savefig("%s/bandwidth.png" % dirname, format="png")

        # agora vamos gerar o PDF
        print_fd = open("%s/bandwidth.txt" % (dirname), "w")
        print >>print_fd, "=%s/bandwidth.png" % (dirname)
        for z in lines:
            print >>print_fd, z
        print_fd.close()

    def multicast(self, dirname, machines, num_msgs, bandwidth, type="multicast"):
        """Inicia a captura"""
        for band in bandwidth:
            # avalia o tipo de experimento
            if type == "multicast":
                START_CMD = COMMAND_BANDWIDTH_MULTICAST_START
                STOP_CMD = COMMAND_BANDWIDTH_MULTICAST_STOP
                ADDR = MCASTADDR
                PORT = MCASTPORT
                SOCK_FUNC = sock_mcast
                EXT = "mcast"
            else:
                START_CMD = COMMAND_BANDWIDTH_BROADCAST_START
                STOP_CMD = COMMAND_BANDWIDTH_BROADCAST_STOP
                ADDR = BCASTADDR
                PORT = BCASTPORT
                SOCK_FUNC = sock_bcast
                EXT = "bcast"

            print "Captura iniciada"
            self.gui.multicast_started()
            # Envia as mensagens
            for z in machines:
                self.gui.show_progress(_("Sending %s Bandwidth test request to %s") % (type, z))
                print "Enviando para %s" % z
                # enviando mensagem para cliente para iniciar a captura
                s = connect(z, LISTENPORT, timeout=5)
                if not s:
                    print _("Erro conectando a %s!" % z)
                    traceback.print_exc()
                    # Marca a maquina como offline
                    self.gui.set_offline(z)
                # envia a mensagem
                try:
                    s.send(struct.pack("<b", START_CMD))
                    s.close()
                except:
                    print _("Erro enviando mensagem para %s: %s" % (z, sys.exc_value))
                    traceback.print_exc()
                    # Marca a maquina como offline
                    self.gui.set_offline(z)
            # Agora faz o experimento
            self.gui.show_progress(_("Starting %s experiment in 2..") % type)

            # aguarda um tempo para os clientes se estabilizarem
            time.sleep(1)
            self.gui.show_progress(_("Starting %s experiment in 1..") % type)
            time.sleep(1)

            # TODO: calcular delays de acordo com o tempo de envio de pacote
            if band > 0:
                delay = 1 / (
                                (
                                    (band * 1024) / 8.0
                                ) / DATAGRAM_SIZE
                            )
            else:
                delay = 0
            print "Delay between messages: %f" % delay
            data = " " * (DATAGRAM_SIZE - struct.calcsize("<I"))
            try:
                for z in range(num_msgs):
                    packet = struct.pack("<I", z)
                    s = SOCK_FUNC()
                    t1 = timefunc()
                    s.sendto(packet + data, (ADDR, PORT))
                    t2 = timefunc()
                    curdelay = delay - (t2 - t1);
                    if curdelay > 0:
                        time.sleep(delay)
                    if (z % 100) == 0:
                        self.gui.show_progress(_("Sending data (%d Kbps): %d/%d") % (band, z, num_msgs))
            except:
                traceback.print_exc()
                self.gui.show_progress(_("Error sending %s message: %s") % (type, sys.exc_value))


            self.gui.show_progress(_("Sending %s Bandwidth finish request") % type)
            # Desconecta os clientes
            for z in machines:
                print "Enviando para %s" % z
                # enviando mensagem para cliente para iniciar a captura
                s = connect(z, LISTENPORT, timeout=3)
                if not s:
                    print _("Erro conectando a %s!" % z)
                    self.gui.set_offline(z, _("Unable to connect to %s!") % z)
                # envia a mensagem
                try:
                    s.send(struct.pack("<b", STOP_CMD))
                except:
                    print _("Erro enviando mensagem para %s: %s" % (z, sys.exc_value))
                    self.gui.set_offline(z, _("Error communicating with %s: %s!") % (z, sys.exc_value))
                # agora vamos receber o arquivo
                try:
                    size = struct.unpack("<I",
                            (s.recv(struct.calcsize("<I")))
                            )[0]
                    fd = open("%s/%s.%s.%s" % (dirname, band, z, EXT), "wb")
                    print "Saving results to %s/%s.%s.%s" % (dirname, band, z, EXT)
                    print >>fd, "# total msgs: %d, max bandwidth: %d kbps" % (num_msgs, band)
                    while size > 0:
                        buf = s.recv(size)
                        fd.write(buf)
                        size -= len(buf)
                    print >>fd, "\n"
                    fd.close()
                    s.close()
                except:
                    print _("Erro recebendo arquivo de %s: %s" % (z, sys.exc_value))
                    traceback.print_exc()
                    self.gui.set_offline(z, _("Error while receiving data from %s: %s!") % (z, sys.exc_value))
            self.analyze_mcast(dirname, band, machines, type)
            # Agora recupera os dados de todos
            # TODO: analisar todos
            #if type == "multicast":
            #    self.gui.analyze_mcast(dirname, machines)
            #else:
            #    self.gui.analyze_mcast(dirname, machines, type="Broadcast")
        # Termina o experimento
        self.gui.show_progress(_("Evaluating %s results..") % type)
        self.analyze_group(dirname, bandwidth, type)
        self.gui.show_progress(_("Finished %s experiment") % type)

    def analyze_mcast(self, dirname, band, clients, type="Multicast", doplot=True):
        """Avalia a banda dos clientes"""
        lines = []
        xtitles = []
        messages = []
        timelines = {}
        # para fazer as medias
        losses = {}
        total_sent = 0
        total_recv = 0
        bandwidth=0
        realbandwidth=0

        if len(clients) < 1:
            return

        # gerar o cabecalho
        lines.append(_("%s Bandwidth Evaluation") % type.title())
        lines.append(_("Bandwidth: %s") % band)
        lines.append(_("Clients: %s\n") % (",".join(clients)))

        for client in clients:
            if type == "multicast":
                ext = "mcast"
            else:
                ext = "bcast"
            try:
                data = open("%s/%s.%s.%s" % (dirname, band, client, ext)).readlines()
            except:
                print "Unable to open file for %s" % client
                traceback.print_exc()
                continue
            total_msgs = int(data[0].split(" ")[3].replace("," ,""))
            bandwidth = int(data[0].split(" ")[6])
            received_msgs = int(data[1].split(" ")[3])
            received_frac = float((received_msgs * 100) / total_msgs)

            # atualiza a contagem global
            total_sent += total_msgs
            total_recv += received_msgs

            messages.append(received_frac)
            xtitles.append("%s\n%d sent, %d recv" % (client, total_msgs, received_msgs))

            ids = []
            delays = [float(x.split(" ")[1]) for x in data[2:] if len(x) > 1]
            timelines[client] = (ids, delays)

            if delays:
                meandelay = reduce(lambda x, y: x+y, delays) / len(delays)
            else:
                meandelay = 1
            maxbandwidth = ((1/meandelay) * 8 * 1450) / 1000 # 1024 - kibps

            realbandwidth += maxbandwidth

            losses[client] = (total_msgs, received_msgs, received_frac, maxbandwidth)

        if not total_sent:
            # No data was sent?
            print "Error: no data was sent!"
            return
        total_frac = float((total_recv * 100) / total_sent)
        realbandwidth /= len(clients)

        # creates CSV
        output = open("%s/%s.%s.csv" % (dirname, type, band), "w")
        print >>output, _("Client, sent messages, received messages, received fraction, real bandwidth")
        print >>output, _("Bandwidth, %d, clients, %d") % (bandwidth, len(clients))
        print >>output, "%s, %d, %d, %0.2f, %0.2f" % (_("All clients"), total_sent, total_recv, total_frac, realbandwidth)
        lines.append(_("%s:\n\tSent messages: %d\n\tReceived messages: %d\n\tReception quality: %0.2f %%\n\tBandwidth: %0.2f") % (_("All clients"), total_sent, total_recv, total_frac, realbandwidth))
        for client in losses:
            sent, recv, frac, maxbandwidth = losses[client]
            print >>output, "%s, %d, %d, %0.2f, %0.2f" % (client, sent, recv, frac, maxbandwidth)
            lines.append(_("%s:\n\tSent messages: %d\n\tReceived messages: %d\n\tReception quality: %0.2f %%\n\tBandwidth: %0.2f") % (client, sent, recv, frac, maxbandwidth))
        output.close()

        fig = figure()
        # Generates graph
        ax = fig.add_subplot(111)
        fig.suptitle(_("%s reception quality (%d%% average, %0.2f/%d Kbps)" % (type, total_frac, realbandwidth, bandwidth)))
        ax.bar(range(len(messages)), messages)
        xticks(arange(len(xtitles)), xtitles)
        ylabel(_("Messages received (%)"))
        ax.grid()
        savefig("%s/%s_%s.png" % (dirname, type, band), format="png")

        # gera o arquivo para virar pdf
        print_fd = open("%s/%s_%s.txt" % (dirname, type, band), "w")
        print >>print_fd, "=%s/%s_%s.png" % (dirname, type, band)
        for z in lines:
            print >>print_fd, z
        print_fd.close()

    def analyze_group(self, dirname, bandwidth, type):
        """Analyzes group of multicast/broadcast experiments.
        WARNING: this routing analyzes the .csv files, assuming they are already created.
        This is faster than analyzing individual files (as performed by extract_band),
        but it assumes that the files do exists."""
        # Only makes sense if we have more than one experiment
        if len(bandwidth) < 2:
            return

        try:
            experiments = ["%s/%s.%s.csv" % (dirname, type, z) for z in bandwidth]
        except:
            print _("Unable to parse timestamp list for %s!") % timestamp
            traceback.print_exc()
            return

        lines = []
        xlabels = []
        sizes = []
        values = []
        rates = []
        output = open("%s/%s.csv" % (dirname, type), "w")
        print >>output, "Type, bandwidth, real bandwidth, quality"
        print experiments

        # gerar o cabecalho
        lines.append(_("%s Multiple Bandwidth Evaluation") % type.title())
        lines.append(_("Bandwidth: %s\n") % ",".join([str(x) for x in bandwidth]))

        for exp in experiments:
            try:
                data = open(exp).readlines()[1:3]
                bandwidth = int(data[0].split(",")[1].strip())
                clients = int(data[0].split(",")[3].strip())
                rate = float(data[1].split(",")[3].strip())
                real_bandwidth = float(data[1].split(",")[4].strip())
                xlabels.append(bandwidth)
                values.append(real_bandwidth)
                sizes.append(bandwidth)
                rates.append(rate)
                print >>output, "%s, %d, %0.2f, %0.2f" % (type, bandwidth, real_bandwidth, rate)
                lines.append(_("%d KBps:\n\tObtained bandwidth: %0.2f kbps\n\tReception quality: %0.2f %%") % (bandwidth, real_bandwidth, rate))
            except:
                print "Error parsing %s!" % exp
                traceback.print_exc()
        output.close()

        # Bandwidth figure
        fig = figure()
        ax = fig.add_subplot(111)
        print sizes
        fig.suptitle(_("Bandwidth evaluation (%s) from %d to %d Kbps") % (type, sizes[0], sizes[-1]))
        ax.plot(range(len(sizes)), sizes, '-', label='Expected bandwidth')
        ax.plot(range(len(values)), values, 'r-', label='Real bandwidth')
        xticks(arange(len(xlabels)), xlabels)
        ylabel(_("Bandwidth (Kbps)"))
        ax.grid()
        ax.legend()
        savefig("%s/%s.png" % (dirname, type), format="png")

        # Quality figure
        fig = figure()
        ax = fig.add_subplot(111)
        fig.suptitle(_("Reception quality evaluation (%s) from %d to %d Kbps") % (type, sizes[0], sizes[-1]))
        ax.bar(range(len(rates)), rates)
        xticks(arange(len(xlabels)), xlabels)
        ylabel(_("Messages received (%)"))
        ax.grid()
        savefig("%s/%s_quality.png" % (dirname, type), format="png")

        # gera o arquivo para virar pdf
        print_fd = open("%s/%s.txt" % (dirname, type), "w")
        print >>print_fd, "=%s/%s.png" % (dirname, type)
        print >>print_fd, "=%s/%s_quality.png" % (dirname, type)
        for z in lines:
            print >>print_fd, z
        print_fd.close()

    def start_capture(self, dirname, machines):
        """Inicia a captura"""

        # atualiza o timestamp do experimento
        self.capturedir = dirname

        fd = open("dirname/results.txt" % dirname, "w")
        fd.write("%s\n" % dirname)
        fd.close()

        for z in machines:
            print "Enviando para %s" % z
            # enviando mensagem para cliente para iniciar a captura
            s = connect(z, LISTENPORT, timeout=5)
            if not s:
                print _("Erro conectando a %s!" % z)
                self.gui.set_offline(z, _("Unable to connect to %s!") % z)
            # envia a mensagem
            try:
                s.send(struct.pack("<b", COMMAND_START_CAPTURE))
                # envia o timestamp do experimento e a descricao
                s.send(struct.pack("10s32s", dirname, dirname))
            except:
                print _("Erro enviando mensagem para %s: %s" % (z, sys.exc_value))
                self.gui.set_offline(z, _("Error communicating with %s: %s!") % (z, sys.exc_value))
            s.close()
        print "Captura iniciada"
        self.gui.capture_started()

    def stop_capture(self, machines):
        """Termina a captura"""
        for z in machines:
            print "Enviando para %s" % z
            # enviando mensagem para cliente para iniciar a captura
            s = connect(z, LISTENPORT, timeout=3)
            if not s:
                print _("Erro conectando a %s!" % z)
                self.gui.set_offline(z, _("Unable to connect to %s!") % z)
            # envia a mensagem
            try:
                s.send(struct.pack("<b", COMMAND_STOP_CAPTURE))
            except:
                print _("Erro enviando mensagem para %s: %s" % (z, sys.exc_value))
                self.gui.set_offline(z, _("Error communicating with %s: %s!") % (z, sys.exc_value))
            # agora vamos receber o arquivo
            try:
                size = struct.unpack("<I",
                        (s.recv(struct.calcsize("<I")))
                        )[0]
                print size
                if size > 0:
                    print "Recebendo arquivo de %d bytes de %s" % (size, z)
                fd = open("%s/%s.pcap" % (self.capturedir, z), "wb")
                while size > 0:
                    buf = s.recv(size)
                    fd.write(buf)
                    size -= len(buf)
                fd.close()
            except:
                print _("Erro recebendo arquivo de %s: %s" % (z, sys.exc_value))
                traceback.print_exc()
                self.gui.set_offline(z, _("Error while receiving data from %s: %s!") % (z, sys.exc_value))
            s.close()
            # Agora vamos esperar a resposta..
        print "Captura finalizada"

    def run(self):
        """Starts a background thread"""
        while 1:
            experiment = self.experiments.get()
            if not experiment:
                continue
            # chegou ALGO
            name, comments, parameters = experiment
            print "Running %s (%s)" % (name, comments)
            if name == "bandwidth":
                self.bandwidth(comments, parameters)
                self.gui.finish_bandwidth()
            elif name == "start_capture":
                machines = parameters
                self.start_capture(comments, machines)
            elif name == "stop_capture":
                self.stop_capture(parameters)
                self.gui.capture_finished()
            elif name == "multicast":
                machines, num_msgs, bandwidth = parameters
                self.multicast(comments, machines, num_msgs, bandwidth)
                self.gui.multicast_finished()
            elif name == "broadcast":
                machines, num_msgs, bandwidth = parameters
                self.multicast(comments, machines, num_msgs, bandwidth, type="broadcast")
                self.gui.multicast_finished()
            elif name == "report":
                logfiles = ["%s/%s" % (comments, f) for f in parameters]
                print "Generating report in %s/results.pdf: [%s]" % (comments, ",".join(logfiles))
                self.gui.show_progress(_("Generating report in %s/results.pdf") % (comments))
                self.report_writer.report(comments, logfiles)
            elif name == "quick":
                # Quick experiment
                # Should take around 2 minutes
                # 1: Multicast Test: from 400 to 2000, with step of 400, and using 400 messages
                machines = parameters
                if len(machines) < 1:
                    self.gui.show_progress(_("Error: no machines to evaluate, aborting."))
                    self.gui.finish_quick()
                    return
                bandwidth = range(400, 2001, 400)
                # prepare logfiles
                self.multicast(comments, machines, 400, bandwidth)
                # vamos ver os arquivos de log
                logfiles = ["%s/multicast.txt" % comments]
                self.gui.show_progress(_("Generating final report.."))
                self.report_writer.report(comments, logfiles)
                self.gui.show_progress(_("Quick test finished!"))
                self.gui.finish_quick()
            elif name == "full":
                # Full experiment
                # Should take around 2 minutes
                # 1: TCP Bandwidth test
                # 1: Multicast Test: from 400 to 4000, with step of 200, and using 100 messages
                machines = parameters
                if len(machines) < 1:
                    self.gui.show_progress(_("Error: no machines to evaluate, aborting."))
                    self.gui.finish_full()
                    return
                bandwidth = range(400, 4001, 200)
                # prepare logfiles
                self.bandwidth(comments, machines)
                self.multicast(comments, machines, 1000, bandwidth)
                # vamos ver os arquivos de log
                logfiles = ["bandwidth.txt", "multicast.txt"]
                logfiles.extend(["multicast_%d.txt" % band for band in bandwidth])
                logfiles = ["%s/%s" % (comments, f) for f in logfiles]
                self.gui.show_progress(_("Generating final report.."))
                self.report_writer.report(comments, logfiles)
                self.gui.show_progress(_("Full test finished!"))
                self.gui.finish_full()
            else:
                print "Unknown experiment %s" % name
# }}}

# {{{ TrafdumpGui
class TrafdumpGui:
    selected_machines = 0
    """Teacher GUI main class"""
    def __init__(self, guifile):
        """Initializes the interface"""
        # inter-class communication
        self.new_clients_queue = Queue.Queue()
        # colors
        self.color_normal = gtk.gdk.color_parse("#99BFEA")
        self.color_active = gtk.gdk.color_parse("#FFBBFF")
        self.color_background = gtk.gdk.color_parse("#FFFFFF")

        self.wTree = gtk.glade.XML(guifile)

        # Callbacks
        dic = {
                "on_MainWindow_destroy": self.on_MainWindow_destroy # fecha a janela principal
                }
        self.wTree.signal_autoconnect(dic)

        # tooltips
        self.tooltip = gtk.Tooltips()

        # Muda o background
        self.MainWindow.modify_bg(gtk.STATE_NORMAL, self.color_background)
        self.MachineLayout.modify_bg(gtk.STATE_NORMAL, self.color_background)

        # Configura os botoes
        self.QuitButton.connect('clicked', self.on_MainWindow_destroy)
        self.SelectAllButton.connect('clicked', self.select_all)
        self.UnselectAllButton.connect('clicked', self.unselect_all)
        self.StartCapture.connect('clicked', self.start_capture)
        self.StopCapture.connect('clicked', self.stop_capture)
        self.BandwidthButton.connect('clicked', self.bandwidth)
        self.MulticastButton.connect('clicked', self.multicast)
        self.BroadcastButton.connect('clicked', self.multicast, "broadcast")
        self.QuickTest.connect('clicked', self.quick_test)
        self.FullTest.connect('clicked', self.full_test)

        # Configura o timer
        gobject.timeout_add(1000, self.monitor)

        # Inicializa a matriz de maquinas
        self.machine_layout = [None] * MACHINES_X
        for x in range(0, MACHINES_X):
            self.machine_layout[x] = [None] * MACHINES_Y

        self.machines = {}

        # Mostra as maquinas
        self.MachineLayout.show_all()

        # inicializa o servico
        self.service = None

        # all done
        self.show_progress(_("Trafdump ready!"))

    def set_service(self, service):
        """Determines the active benchmarking service"""
        self.service = service

    def quick_test(self, widget):
        """Runs the quick test"""
        print "Quick test"
        experiment_name = self.question(_("This will run the Quick Test, which should take around 2 minutes.\n\nExperiment description:"), _("Quick experiment"))
        if not experiment_name:
            return
        dirname = mkresults(experiment_name)
        if not dirname:
            print "Error: unable to create results directory for '%s'!" % experiment_name
            return

        machines = []
        for z in self.machines:
            img = self.machines[z].button.get_image()
            if img == self.machines[z].button.img_on:
                machines.append(z)

        self.service.experiments.put(("quick", dirname, machines))
        self.toggle_widgets(False)

    def finish_quick(self):
        """Quick experiment finished"""
        print "Quick experiment finished!"""
        self.toggle_widgets(True)

    def full_test(self, widget):
        """Runs the full test"""
        print "Full test"
        experiment_name = self.question(_("This will run the Full Test, which could take more than 10 minutes.\n\nExperiment description:"), _("Quick experiment"))
        if not experiment_name:
            return
        dirname = mkresults(experiment_name)
        if not dirname:
            print "Error: unable to create results directory for '%s'!" % experiment_name
            return

        machines = []
        for z in self.machines:
            img = self.machines[z].button.get_image()
            if img == self.machines[z].button.img_on:
                machines.append(z)

        self.service.experiments.put(("full", dirname, machines))
        self.toggle_widgets(False)

    def finish_full(self):
        """Full experiment finished"""
        print "Full experiment finished!"""
        self.toggle_widgets(True)

    def analyze(self, widget):
        """Analyzes the results"""

        def analyze_details(exp, timestamp, clients, doplot=True):
            """Which function to use?"""
            if exp == "band":
                self.analyze_bandwidth(timestamp, clients, doplot=doplot)
            elif exp == "mcast":
                self.analyze_mcast(timestamp, clients, doplot=doplot)
            elif exp == "bcast":
                self.analyze_mcast(timestamp, clients, type="Broadcast", doplot=doplot)
            elif exp == "group":
                self.analyze_group(timestamp, clients, doplot=doplot)
            else:
                print "Unknown experiment %s" % exp

        # monta a lista de resultados
        dialog = gtk.Dialog(_("Select experiment"), self.MainWindow, 0,
                (gtk.STOCK_OK, gtk.RESPONSE_OK,
                gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL))

        combobox = gtk.combo_box_new_text()
        combobox.append_text(_("Batch-process all experiments"))

        results = glob.glob("results*txt")
        experiments = []
        for r in results:
            ret = res_r.findall(r)
            if not ret:
                continue
            timestamp = ret[0]
            title = open(r).readline().strip()
            experiments.append(timestamp)
            combobox.append_text("%s: %s" % (printts(timestamp), title))
        combobox.set_active(0)
        dialog.vbox.add(combobox)

        dialog.show_all()
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            dialog.destroy()
            exp = combobox.get_active()
        else:
            dialog.destroy()
            return

        # TODO: can be refactored..

        # processa todos os experimentos?
        if exp == 0:
            # faz todos
            for timestamp in experiments:
                exp, clients = find_clients(timestamp)
                if not exp:
                    print _("No clients found for experimento %s") % timestamp
                    continue
                print _("Batch-analyzing %s (%s, %s)") % (timestamp, exp, str(clients))
                analyze_details(exp, timestamp, clients, doplot=False)
            return

        # agora faz experimentos especificos
        timestamp = experiments[exp - 1]

        exp, allclients = find_clients(timestamp)
        if not exp:
            # no files found
            print "No clients found!"
            return

        client_selected = 0
        if len(allclients) > 1:
            # mostra o dialogo para escolher os clientes
            dialog = gtk.Dialog(_("Select clients"), self.MainWindow, 0,
                    (gtk.STOCK_OK, gtk.RESPONSE_OK,
                    gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL))
            dialog.vbox.add(gtk.Label(_("Select clients to process")))

            combobox = gtk.combo_box_new_text()
            combobox.append_text(_("All clients"))

            for client in allclients:
                combobox.append_text(client)

            combobox.set_active(0)
            dialog.vbox.add(combobox)

            dialog.show_all()
            response = dialog.run()
            if response == gtk.RESPONSE_OK:
                dialog.destroy()
                client_selected = combobox.get_active()
            else:
                dialog.destroy()
                return

        if client_selected == 0:
            clients = allclients
        else:
            clients = [allclients[client_selected - 1]]

        # agora calcula os resultados
        print _("Analyzing %s (%s, %s)") % (timestamp, exp, str(clients))
        analyze_details(exp, timestamp, clients, doplot=True)

    def show_fig(self, fig):
        """Shows a pylab figure"""
        win = gtk.Window()
        win.connect("destroy", lambda w: w.destroy())
        win.set_default_size(640, 480)
        win.set_title(_("Results"))

        vbox = gtk.VBox()
        win.add(vbox)

        sw = gtk.ScrolledWindow()
        vbox.add(sw)

        # A scrolled window border goes outside the scrollbars and viewport
        sw.set_border_width (10)
        # policy: ALWAYS, AUTOMATIC, NEVER
        sw.set_policy (hscrollbar_policy=gtk.POLICY_AUTOMATIC,
                       vscrollbar_policy=gtk.POLICY_AUTOMATIC)

        canvas = FigureCanvas(fig)
#        canvas.set_size_request(600 + (10 * len(clients)), 400)
        sw.add_with_viewport(canvas)
        toolbar = NavigationToolbar(canvas, win)
        vbox.pack_start(toolbar, False, False)

        gobject.idle_add(win.show_all)

    def question(self, title, input=None):
        """Asks a question :)"""
        # cria a janela do dialogo
        dialog = gtk.Dialog(_("Question"), self.MainWindow, 0,
                (gtk.STOCK_OK, gtk.RESPONSE_OK,
                gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL))
        dialogLabel = gtk.Label(title)
        dialog.vbox.add(dialogLabel)
        dialog.vbox.set_border_width(8)
        if input:
            entry = gtk.Entry()
            entry.set_text(input)
            dialog.vbox.add(entry)
        dialog.show_all()
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            dialog.destroy()
            if input:
                return entry.get_text()
            else:
                return True
        else:
            dialog.destroy()
            return None

    def show_progress(self, message):
        """Shows a message :)"""
        gtk.gdk.threads_enter()
        # Status
        self.StatusLabel.set_text(message)
        # Log
        buffer = self.LogView.get_buffer()
        iter = buffer.get_end_iter()
        buffer.insert(iter, "%s: %s\n" % (time.asctime(), message))
        self.LogView.scroll_to_iter(iter, 0)
        # XXX: we hand here.. :(
        #self.MainWindow.show_all()
        #while gtk.events_pending():
        #    gtk.main_iteration(False)
        gtk.gdk.threads_leave()

    def put_machine(self, machine):
        """Puts a client machine in an empty spot"""
        for y in range(0, MACHINES_Y):
            for x in range(0, MACHINES_X):
                if not self.machine_layout[x][y]:
                    self.machine_layout[x][y] = machine
                    self.MachineLayout.put(machine, x * STEP_X, y * STEP_Y)
                    # verify scroll size
                    width, height = self.MachineLayout.get_size()
                    if height < (y+1) * STEP_Y:
                        self.MachineLayout.set_size(width, (y+1) * STEP_Y)
                    machine.machine_x = x
                    machine.machine_y = y
                    return
        print "Not enough layout space to add a machine!"

    def monitor(self):
        """Monitors new machines connections"""
        #self.StatusLabel.set_markup("<b>Link:</b> %s, <b>Signal:</b> %s, <b>Noise:</b> %s" % (link, level, noise))
        while not self.new_clients_queue.empty():
            addr = self.new_clients_queue.get()
            if addr not in self.machines:
                # Maquina nova
                gtk.gdk.threads_enter()
                machine = self.mkmachine("%s" % addr)
                machine.button.connect('clicked', self.cb_machine, machine)
                self.put_machine(machine)
                self.machines[addr] = machine
                machine.show_all()
                gtk.gdk.threads_leave()
                self.show_progress(_("Found %s (%d machines connected)!") % (addr, len(self.machines)))
            else:
                machine = self.machines[addr]
                self.tooltip.set_tip(machine, _("Updated on %s" % (time.asctime())))

        return True

    def set_offline(self, machine, message=None):
        """Marks a machine as offline"""
        if machine not in self.machines:
            print "Error: machine %s not registered!" % machine
            return
        gtk.gdk.threads_enter()
        self.machines[machine].button.set_image(self.machines[machine].button.img_off)
        if message:
            self.tooltip.set_tip(self.machines[machine], _("%s\%s!") % (time.asctime(), message))
        gtk.gdk.threads_leave()
        if message:
            self.show_progress(message)
        else:
            self.show_progress(_("Lost connection to %s") % machine)

    def start_bandwidth(self):
        """Bandwidth experiment started"""
        print "Bandwidth experiment started!"""
        self.toggle_widgets(False)

    def finish_bandwidth(self):
        """Bandwidth experiment finished"""
        print "Bandwidth experiment finished!"""
        self.toggle_widgets(True)

    def capture_started(self):
        """Traffic experiment started"""
        print "Capture started!"""
        gtk.gdk.threads_enter()
        self.StartCapture.set_sensitive(False)
        self.StopCapture.set_sensitive(True)
        gtk.gdk.threads_leave()

    def capture_finished(self):
        """Traffic experiment finished"""
        print "Capture finished!"""
        gtk.gdk.threads_enter()
        self.StartCapture.set_sensitive(True)
        self.StopCapture.set_sensitive(False)
        gtk.gdk.threads_leave()

    def toggle_widgets(self, value):
        """Disables the interface actions"""
        for widget in [self.BandwidthButton,
                        self.MulticastButton,
                        self.BroadcastButton,
                        self.BandwidthButton,
                        self.QuickTest,
                        self.FullTest]:
            widget.set_sensitive(value)

    def multicast(self, widget, type="multicast"):
        """Inicia o teste de multicast"""
        experiment_name = self.question(_("Experiment description:"), _("%s experiment") % type)
        if not experiment_name:
            return
        dirname = mkresults(experiment_name)
        if not dirname:
            print "Error: unable to create results directory for '%s'!" % experiment_name
            return

        num_msgs = self.question(_("How many multicast messages to send?"), "1000")
        if not num_msgs:
            return
        try:
            num_msgs = int(num_msgs)
        except:
            return

        bandwidth = self.question(_("Maximum bandwidth in Kbps (0 for no limit)\nor\nBandwidth range (format: minimum bandwidth, maximum bandwidth, interval)"), "0")
        if not bandwidth:
            return
        try:
            try:
                band_min, band_max, band_int = bandwidth.split(",", 3)
                band_min = int(band_min.strip())
                band_max = int(band_max.strip())
                band_int = int(band_int.strip())
                steps = (band_max - band_min) / band_int + 1
                bandwidth = [band_min + (band_int * step) for step in range(steps)]
            except:
                bandwidth = [int(bandwidth)]
        except:
            return

        print "Bandwidth to estimate: %s Kbps" % (bandwidth)

        machines = []
        for z in self.machines:
            img = self.machines[z].button.get_image()
            if img == self.machines[z].button.img_on:
                machines.append(z)

        self.service.experiments.put((type, dirname, (machines, num_msgs, bandwidth)))
        # geracao de PDF
        logfiles = []
        if len(bandwidth) > 1:
            logfiles.append("%s.txt" % type)
        logfiles.extend(["%s_%d.txt" % (type, band) for band in bandwidth])
        self.service.experiments.put(("report", dirname, logfiles))

    def multicast_started(self):
        """Multicast experiment has started"""
        self.toggle_widgets(False)

    def multicast_finished(self):
        """Multicast experiment has finished"""
        self.toggle_widgets(True)

    def broadcast_started(self):
        """Broadcast experiment has started"""
        self.toggle_widgets(False)

    def broadcast_finished(self):
        """Broadcast experiment has finished"""
        self.toggle_widgets(True)

    def bandwidth(self, widget):
        """Inicia a captura"""
        # TODO: perguntar o nome do experimento
        experiment_name = self.question(_("Experiment description:"), _("Throughput experiment"))
        if not experiment_name:
            return
        dirname = mkresults(experiment_name)
        if not dirname:
            print "Error: unable to create results directory for '%s'!" % experiment_name
            return
        self.BandwidthButton.set_sensitive(False)

        machines = []
        for z in self.machines:
            img = self.machines[z].button.get_image()
            if img == self.machines[z].button.img_on:
                machines.append(z)

        self.service.experiments.put(("bandwidth", dirname, machines))
        self.service.experiments.put(("report", dirname, ["bandwidth.txt"]))

    def start_capture(self, widget):
        """Inicia a captura"""
        # TODO: perguntar o nome do experimento
        experiment_name = self.question(_("Describe the experiment"), _("Sample traffic collection"))
        if not experiment_name:
            return

        machines = []
        for z in self.machines:
            img = self.machines[z].button.get_image()
            if img == self.machines[z].button.img_on:
                machines.append(z)
        self.service.experiments.put(("start_capture", experiment_name, machines))

    def stop_capture(self, widget):
        """Termina a captura"""
        machines = []
        for z in self.machines:
            img = self.machines[z].button.get_image()
            if img == self.machines[z].button.img_on:
                machines.append(z)
        self.service.experiments.put(("stop_capture", "", machines))
        print "Captura finalizada"

    def select_all(self, widget):
        """Selects all machines"""
        for z in self.machines.values():
            z.button.set_image(z.button.img_on)

    def unselect_all(self, widget):
        """Selects all machines"""
        for z in self.machines.values():
            z.button.set_image(z.button.img_off)

    def __getattr__(self, attr):
        """Requests an attribute from Glade"""
        obj = self.wTree.get_widget(attr)
        if not obj:
            #bluelab_config.error("Attribute %s not found!" % attr)
            return None
        else:
            return obj

    def on_MainWindow_destroy(self, widget):
        """Main window was closed"""
        gtk.main_quit()
        sys.exit(0)

    def get_img(self, imgpath):
        """Returns image widget if exists"""
        try:
            fd = open(imgpath)
            fd.close()
            img = gtk.Image()
            img.set_from_file(imgpath)
        except:
            img=None
        return img

    def mkmachine(self, name, img="machine.png", img_offline="machine_off.png", status="online"):
        """Creates a client representation"""
        box = gtk.VBox(homogeneous=False)

        imgpath = "iface/%s" % (img)
        imgpath_off = "iface/%s" % (img_offline)

        img = self.get_img(imgpath)
        img_off = self.get_img(imgpath_off)

        button = gtk.Button()
        button.img_on = img
        button.img_off = img_off
        button.machine = name
        if status=="online":
            button.set_image(button.img_on)
        else:
            button.set_image(button.img_off)
        box.pack_start(button, expand=False)

        label = gtk.Label(_("name"))
        label.set_use_markup(True)
        label.set_markup("<small>%s</small>" % name)
        box.pack_start(label, expand=False)

        self.tooltip.set_tip(box, name)
#        box.set_size_request(52, 52)

        # Sets private variables
        box.machine = name
        box.button = button
        box.label = label
        box.wifi = None
        return box

    def cb_machine(self, widget, machine):
        """Callback when clicked on a client machine"""
        img = machine.button.get_image()
        if img == machine.button.img_off:
            machine.button.set_image(machine.button.img_on)
        else:
            machine.button.set_image(machine.button.img_off)

        # muda o texto

    def mkbutton(self, img, img2, text, action, color_normal, color_active):
        """Creates a callable button"""
        box = gtk.HBox(homogeneous=False)
        # Imagem 1
        imgpath = "%s/%s" % (self.appdir, img)
        # Verifica se arquivo existe
        try:
            fd = open(imgpath)
            fd.close()
        except:
            imgpath=None
        if imgpath:
            img = gtk.Image()
            img.set_from_file(imgpath)
            box.pack_start(img, expand=False)

        # Verifica se arquivo existe
        try:
            fd = open(imgpath)
            fd.close()
        except:
            imgpath=None
        if imgpath:
            img2 = gtk.Image()
            img2.set_from_file(imgpath)

        # Texto
        label = gtk.Label(text)
        label.set_use_markup(True)
        label.set_markup("<b>%s</b>" % text)
        box.pack_start(label, expand=False)

        button = gtk.Button()
        button.modify_bg(gtk.STATE_NORMAL, color_normal)
        button.modify_bg(gtk.STATE_PRELIGHT, color_active)

        button.add(box)

        # callback
        if action:
            button.connect('clicked', action, "")
        button.show_all()
        return button
# }}}

# {{{ TrafBroadcast
class TrafBroadcast(Thread):
    """Broadcast-related services"""
    def __init__(self, port, gui):
        """Initializes listening thread"""
        Thread.__init__(self)
        self.port = port
        self.gui = gui

    def run(self):
        """Starts listening to broadcast"""
        class BcastHandler(SocketServer.DatagramRequestHandler):
            """Handles broadcast messages"""
            def handle(self):
                """Receives a broadcast message"""
                client = self.client_address[0]
#                print " >> Heartbeat from %s!" % client
                global gui
                gui.new_clients_queue.put(client)
        self.socket_bcast = SocketServer.UDPServer(('', self.port), BcastHandler)
        while 1:
            try:
                self.socket_bcast.handle_request()
            except socket.timeout:
                print "Timeout caught!"
                continue
            except:
                print "Error handling broadcast socket!"
                break
# }}}

if __name__ == "__main__":
    # configura o timeout padrao para sockets
    socket.setdefaulttimeout(5)
    gtk.gdk.threads_init()
    print _("Starting broadcast..")
    # Main interface
    gui = TrafdumpGui("iface/trafdump.glade")
    # Benchmarking service
    service = TrafdumpRunner(gui)
    service.start()
    # Broadcasting service
    bcast = TrafBroadcast(LISTENPORT, service)
    bcast.start()

    print _("Starting main loop..")
    gtk.gdk.threads_enter()
    gtk.main()
    gtk.gdk.threads_leave()
