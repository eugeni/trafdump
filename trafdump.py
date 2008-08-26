#!/usr/bin/python
"""
Teacher GUI using GLADE
"""

# TODO: detectar quando conexoes nao sao estabelecidas

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

import gettext
import __builtin__
__builtin__._ = gettext.gettext

from config import *

MACHINES_X = 8
MACHINES_Y = 8

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

        # experiments queue
        self.experiments = Queue.Queue()

    def bandwidth(self, machines):
        """Inicia a captura"""

        timestamp_bandwidth = str(int(time.time()))

        fd = open("results.%s.txt" % timestamp_bandwidth, "w")
        fd.write(_("TCP Bandwidth evaluation experiment.\nClients: %s") % ",".join(machines))
        fd.close()

        print "Captura iniciada"
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
                t1 = time.time()
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
                t2 = time.time()
                time_up = t2 - t1
                bandwidth_up = float(BANDWIDTH_BUFSIZE / time_up)
                print "Upload bandwidth: %f (%f sec)" % (bandwidth_up, time_up)
                self.gui.show_progress(_("TCP Bandwidth test for %s: download") % z)
                t3 = time.time()
                tosend = BANDWIDTH_BUFSIZE
                # temporary packet
                while tosend > 0:
                    data = s.recv(65536)
                    if not data:
                        print "Error: no data received!"
                        return
                    tosend -= len(data)
                t4 = time.time()
                s.close()
                time_down = t4 - t3
                bandwidth_down = float(BANDWIDTH_BUFSIZE / time_down)
                print "Download bandwidth: %f (%f sec)" % (bandwidth_down, time_down)
                fd = open("results.%s.%s.band" % (timestamp_bandwidth, z), "w")
                fd.write("Buffer size: %d\nUpload: %f sec, %f bytes/sec\nDownload: %f sec, %f bytes/sec\n" % (BANDWIDTH_BUFSIZE, time_up, bandwidth_up, time_down, bandwidth_down))
                fd.close()
            except:
                print _("Erro enviando mensagem para %s: %s" % (z, sys.exc_value))
                traceback.print_exc()
                # Marca a maquina como offline
                self.gui.set_offline(z)
        self.gui.show_progress(_("TCP Bandwidth test for %s finished") % z)
        self.gui.finish_bandwidth()

    def multicast(self, machines, num_msgs, bandwidth):
        """Inicia a captura"""

        timestamp_bandwidth = str(int(time.time()))

        fd = open("results.%s.txt" % timestamp_bandwidth, "w")
        fd.write(_("Multicast Bandwidth evaluation.\nClients: %s") % ",".join(machines))
        fd.close()

        print "Captura iniciada"
        # Envia as mensagens
        for z in machines:
            self.gui.show_progress(_("Sending Multicast Bandwidth test request to %s") % z)
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
                s.send(struct.pack("<b", COMMAND_BANDWIDTH_MULTICAST_START))
            except:
                print _("Erro enviando mensagem para %s: %s" % (z, sys.exc_value))
                traceback.print_exc()
                # Marca a maquina como offline
                self.gui.set_offline(z)
            s.close()
        # Agora faz o experimento
        self.gui.show_progress(_("Started multicasting experiment"))

        # aguarda um tempo para os clientes se estabilizarem
        time.sleep(2)

        # TODO: calcular delays de acordo com o tempo de envio de pacote
        if bandwidth > 0:
            delay = 1 / (
                            (
                                (bandwidth * 1024) / 8.0
                            ) / DATAGRAM_SIZE
                        )
        else:
            delay = 0
        print "Delay between messages: %f" % delay
        data = " " * DATAGRAM_SIZE
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_IP)
            s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            for z in range(num_msgs):
                packet = struct.pack("<I", z)
                s.sendto(packet + data, (MCASTADDR, MCASTPORT))
                if delay > 0:
                    time.sleep(delay)
                if (z % 100) == 0:
                    self.gui.show_progress(_("Sending message %d/%d") % (z, num_msgs))
        except:
            traceback.print_exc()
            self.gui.show_progress(_("Error sending multicast message: %s") % sys.exc_value)


        self.gui.show_progress(_("Sending Multicast Bandwidth finish request to %s") % z)
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
                s.send(struct.pack("<b", COMMAND_BANDWIDTH_MULTICAST_STOP))
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
                fd = open("results.%s.%s.mcast" % (timestamp_bandwidth, z), "wb")
                while size > 0:
                    buf = s.recv(size)
                    fd.write(buf)
                    size -= len(buf)
                print >>fd, "\n"
                fd.close()
            except:
                print _("Erro recebendo arquivo de %s: %s" % (z, sys.exc_value))
                traceback.print_exc()
                self.gui.set_offline(z, _("Error while receiving data from %s: %s!") % (z, sys.exc_value))
            finally:
                s.close()
        self.gui.multicast_finished()
        # Agora recupera os dados de todos
        self.gui.show_progress(_("Finished multicasting experiment"))

    def broadcast(self, machines, num_msgs, bandwidth):
        """Inicia a captura de dados broadcast"""

        timestamp_bandwidth = str(int(time.time()))

        fd = open("results.%s.txt" % timestamp_bandwidth, "w")
        fd.write(_("Broadcast Bandwidth evaluation.\nClients: %s") % ",".join(machines))
        fd.close()

        print "Captura iniciada"
        # Envia as mensagens
        for z in machines:
            self.gui.show_progress(_("Sending Broadcast Bandwidth test request to %s") % z)
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
                s.send(struct.pack("<b", COMMAND_BANDWIDTH_BROADCAST_START))
            except:
                print _("Erro enviando mensagem para %s: %s" % (z, sys.exc_value))
                traceback.print_exc()
                # Marca a maquina como offline
                self.gui.set_offline(z)
            s.close()
        # Agora faz o experimento
        self.gui.show_progress(_("Started broadcasting experiment"))

        # aguarda um tempo para os clientes se estabilizarem
        time.sleep(2)

        # TODO: calcular delays de acordo com o tempo de envio de pacote
        if bandwidth > 0:
            delay = 1 / (
                            (
                                (bandwidth * 1024) / 8.0
                            ) / DATAGRAM_SIZE
                        )
        else:
            delay = 0
        print "Delay between messages: %f" % delay
        data = " " * DATAGRAM_SIZE
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_IP)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            for z in range(num_msgs):
                packet = struct.pack("<I", z)
                s.sendto(packet + data, ("255.255.255.255", BCASTPORT))
                if delay > 0:
                    time.sleep(delay)
                if (z % 100) == 0:
                    self.gui.show_progress(_("Sending message %d/%d") % (z, num_msgs))
        except:
            traceback.print_exc()
            self.gui.show_progress(_("Error sending broadcast message: %s") % sys.exc_value)


        self.gui.show_progress(_("Sending Broadcast Bandwidth finish request to %s") % z)
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
                s.send(struct.pack("<b", COMMAND_BANDWIDTH_BROADCAST_STOP))
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
                fd = open("results.%s.%s.bcast" % (timestamp_bandwidth, z), "wb")
                while size > 0:
                    buf = s.recv(size)
                    fd.write(buf)
                    size -= len(buf)
                print >>fd, "\n"
                fd.close()
            except:
                print _("Erro recebendo arquivo de %s: %s" % (z, sys.exc_value))
                traceback.print_exc()
                self.gui.set_offline(z, _("Error while receiving data from %s: %s!") % (z, sys.exc_value))
            finally:
                s.close()
        self.gui.broadcast_finished()
        # Agora recupera os dados de todos
        self.gui.show_progress(_("Finished broadcasting experiment"))

    def start_capture(self, machines, descr):
        """Inicia a captura"""

        # atualiza o timestamp do experimento
        self.curtimestamp = str(int(time.time()))

        fd = open("results.%s.txt" % self.curtimestamp, "w")
        fd.write("%s\n" % descr)
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
                print self.curtimestamp
                s.send(struct.pack("10s32s", self.curtimestamp, descr))
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
                fd = open("results.%s.%s.pcap" % (self.curtimestamp, z), "wb")
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
        self.gui.capture_finished()

    def run(self):
        """Starts a background thread"""
        while 1:
            experiment = self.experiments.get()
            if not experiment:
                continue
            # chegou ALGO
            name, parameters = experiment
            print "Running %s" % name
            if name == "bandwidth":
                self.bandwidth(parameters)
            elif name == "start_capture":
                machines, descr = parameters
                self.start_capture(machines, descr)
            elif name == "stop_capture":
                self.stop_capture(parameters)
            elif name == "multicast":
                machines, num_msgs, bandwidth = parameters
                self.multicast(machines, num_msgs, bandwidth)
            elif name == "broadcast":
                machines, num_msgs, bandwidth = parameters
                self.broadcast(machines, num_msgs, bandwidth)
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
        self.BroadcastButton.connect('clicked', self.broadcast)

        # Configura o timer
        gobject.timeout_add(1000, self.monitor)

        # Inicializa a matriz de maquinas
        self.machine_layout = [None] * MACHINES_X
        for x in range(0, MACHINES_X):
            self.machine_layout[x] = [None] * MACHINES_Y

        self.machines = {}

        # Mostra as maquinas
        self.MachineLayout.show_all()

        # inicializa o timestamp
        self.curtimestamp = 0

        # inicializa o servico
        self.service = None

    def set_service(self, service):
        """Determines the active benchmarking service"""
        self.service = service

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
        self.StatusLabel.set_text(message)
        gtk.gdk.threads_leave()

    def put_machine(self, machine):
        """Puts a client machine in an empty spot"""
        for y in range(0, MACHINES_Y):
            for x in range(0, MACHINES_X):
                if not self.machine_layout[x][y]:
                    self.machine_layout[x][y] = machine
                    self.MachineLayout.put(machine, x * 70, y * 65)
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
                self.StatusLabel.set_text("Found %s (%d machines connected)!" % (addr, len(self.machines)))
                gtk.gdk.threads_leave()
            else:
                machine = self.machines[addr]
                self.tooltip.set_tip(machine, _("Updated on %s" % (time.asctime())))

        gobject.timeout_add(1000, self.monitor)

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

    def finish_bandwidth(self):
        """Bandwidth experiment finished"""
        print "Bandwidth experiment finished!"""
        gtk.gdk.threads_enter()
        self.BandwidthButton.set_sensitive(True)
        gtk.gdk.threads_leave()

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

    def multicast(self, widget):
        """Inicia o teste de multicast"""
        num_msgs = self.question(_("How many multicast messages to send?"), "1000")
        if not num_msgs:
            return
        try:
            num_msgs = int(num_msgs)
        except:
            return

        bandwidth = self.question(_("Maximum bandwidth in Kbps (0 for no limit)?"), "0")
        if not bandwidth:
            return
        try:
            bandwidth = int(bandwidth)
        except:
            return

        self.MulticastButton.set_sensitive(False)

        machines = []
        for z in self.machines:
            img = self.machines[z].button.get_image()
            if img == self.machines[z].button.img_on:
                machines.append(z)

        self.service.experiments.put(("multicast", (machines, num_msgs, bandwidth)))

    def multicast_finished(self):
        """Multicast experiment has finished"""
        self.MulticastButton.set_sensitive(True)

    def broadcast(self, widget):
        """Inicia o teste de broadcast"""
        num_msgs = self.question(_("How many broadcast messages to send?"), "1000")
        if not num_msgs:
            return
        try:
            num_msgs = int(num_msgs)
        except:
            return

        bandwidth = self.question(_("Maximum bandwidth in Kbps (0 for no limit)?"), "0")
        if not bandwidth:
            return
        try:
            bandwidth = int(bandwidth)
        except:
            return
        self.BroadcastButton.set_sensitive(False)

        machines = []
        for z in self.machines:
            img = self.machines[z].button.get_image()
            if img == self.machines[z].button.img_on:
                machines.append(z)

        self.service.experiments.put(("broadcast", (machines, num_msgs, bandwidth)))

    def broadcast_finished(self):
        """Multicast experiment has finished"""
        self.BroadcastButton.set_sensitive(True)

    def bandwidth(self, widget):
        """Inicia a captura"""
        # TODO: perguntar o nome do experimento
        self.BandwidthButton.set_sensitive(False)

        machines = []
        for z in self.machines:
            img = self.machines[z].button.get_image()
            if img == self.machines[z].button.img_on:
                machines.append(z)

        self.service.experiments.put(("bandwidth", machines))

    def start_capture(self, widget):
        """Inicia a captura"""
        # TODO: perguntar o nome do experimento
        descr = self.question(_("Describe the experiment"), _("Sample traffic collection"))
        if not descr:
            return

        machines = []
        for z in self.machines:
            img = self.machines[z].button.get_image()
            if img == self.machines[z].button.img_on:
                machines.append(z)
        self.service.experiments.put(("start_capture", (machines, descr)))

    def stop_capture(self, widget):
        """Termina a captura"""
        machines = []
        for z in self.machines:
            img = self.machines[z].button.get_image()
            if img == self.machines[z].button.img_on:
                machines.append(z)
        self.service.experiments.put(("stop_capture", machines))
        print "Captura finalizada"

    def select_all(self, widget):
        """Selects all machines"""
#        self.question("Pergunta1")
#        ret = self.question("Nome do experimento:", True)
#        print ret
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
