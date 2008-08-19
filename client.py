#!/usr/bin/python
"""
Traffic analysis client.
"""

# TODO:
# - adicionar wireshark no path (!!)
# - imprimir mensagens no log
# - pedir para escolher a interface logo na inicializacao

import sys
import traceback
import time

import socket
import SocketServer
import struct

import os
import logging
import gtk
import gtk.glade
import pygtk
import gobject

from threading import Thread
import socket
import traceback
import time

import gettext
import __builtin__
__builtin__._ = gettext.gettext

from config import *

DEBUG=False

# configuracoes globais
commands = None
ifaces = None
iface_selected = 0

class trafdump:
    selected_machines = 0
    """Teacher GUI main class"""
    def __init__(self, guifile):
        """Initializes the interface"""
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

        # Configura os botoes
        self.QuitButton.connect('clicked', self.on_MainWindow_destroy)

        # Configura o timer
        gobject.timeout_add(1000, self.monitor)

        # configura as interfaces
        self.IfacesBox.set_model(gtk.ListStore(str))
        cell = gtk.CellRendererText()
        self.IfacesBox.pack_start(cell, True)
        self.IfacesBox.add_attribute(cell, 'text', 0)
        self.IfacesBox.append_text(_("Network interface"))
        # Obtem a lista de interfaces disponiveis
        global ifaces
        for z in ifaces.keys():
            self.IfacesBox.append_text(z)
        # acha a interface mais adequada
        # for z in range(len(self.ifaces)):
        #     iface = self.ifaces.keys()[z].strip()
        #     if iface[:3] == "any":
        #         print "found: %d!" % z
        #         print iface
        #         self.IfacesBox.set_active(z + 1)
        self.IfacesBox.set_active(0)
        self.IfacesBox.connect('changed', self.network_selected)
        self.iface = None
        self.outfile = None
        # Inicializa as threads
        self.bcast = BcastSender(LISTENPORT, self)
        self.client = TrafClient(LISTENPORT, self)

    def network_selected(self, combobox):
        """A network interface was selected"""
        combobox.set_sensitive(False)
        model = combobox.get_model()
        index = combobox.get_active()
        global iface_selected
        if index > 0:
            iface_selected = model[index][0]
            gui.log( _("Capturing on %s") % iface_selected)
            gui.log( _("Starting broadcasting service.."))
            self.bcast.start()
            gui.log( _("Starting listening service.."))
            self.client.start()
        else:
            iface_selected = 0
        return

    def monitor(self):
        """Monitors WIFI status"""
        #self.StatusLabel.set_markup("<b>Link:</b> %s, <b>Signal:</b> %s, <b>Noise:</b> %s" % (link, level, noise))
        #gobject.timeout_add(1000, self.monitor)

    def select_all(self, widget):
        """Selects all machines"""
        for z in self.machines:
            z.button.set_image(z.button.img_on)

    def unselect_all(self, widget):
        """Selects all machines"""
        for z in self.machines:
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

    def mkbutton(self, img, img2, text, action, color_normal, color_active): # {{{ Creates a callable button
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

    def log(self, text):
        """Logs a string"""
        buffer = self.textview1.get_buffer()
        iter = buffer.get_iter_at_offset(0)
        print text
        buffer.insert(iter, "%s: %s\n" % (time.asctime(), text))

class BcastSender(Thread):
    """Sends broadcast requests"""
    def __init__(self, port, gui):
        Thread.__init__(self)
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('', 0))
        self.gui = gui

    def run(self):
        """Starts threading loop"""
        print "Running!"
        while 1:
            # TODO: add timers to exit when required
            try:
                if DEBUG:
                    self.gui.log(_("Sending broadcasting message.."))
                self.sock.sendto("hello", ('255.255.255.255', self.port))
                time.sleep(1)
            except:
                gui.log("Error sending broadcast message: %s" % sys.exc_value)
                traceback.print_exc()
                time.sleep(1)

class TrafClient(Thread):
    """Handles server messages"""
    def __init__(self, port, gui):
        """Initializes listening thread"""
        Thread.__init__(self)
        self.port = port
        self.socket_client = None
        self.gui = gui
        gui.outfile = None
        # Determina comandos a utilizar

    def run(self):
        """Starts listening to connections"""
        class MessageHandler(SocketServer.StreamRequestHandler):
            """Handles server messages"""
            def handle(self):
                """Handles incoming requests"""
                addr = self.client_address[0]
                gui.log(_("Received request from %s" % addr))
                msg = self.request.recv(1)
                cmd = struct.unpack('<b', msg)[0]
                if cmd == COMMAND_START_CAPTURE:
                    timestamp = self.request.recv(10)
                    gui.outfile = "%s.pcap" % timestamp
                    descr_r = str(self.request.recv(32))
                    descr = struct.unpack("32s", descr_r)[0]
                    print descr
                    gui.log(_("Starting capture to %s") % (gui.outfile))
                    global iface_selected
                    if iface_selected not in ifaces:
                        gui.log(_("\n!! ERROR!! Capturing interface not selecting, capturing to first available!"))
                        iface_selected = ifaces.keys()[0]
                    iface_idx = ifaces[iface_selected]
                    # Primeiro, vamos parar as capturas antigas
                    run_subprocess(commands["stop"])
                    gui.log(_("Capturing on %s (%s)" % (iface_idx, iface_selected)))
                    run_subprocess(
                            commands["capture"] % {"iface": iface_idx, "output": gui.outfile}
                            )
                elif cmd == COMMAND_STOP_CAPTURE:
                    gui.log(_("Stopping capture"))
                    run_subprocess(commands["stop"])
                    # espera ate salvar tudo
                    time.sleep(1)
                    gui.log(_("Sending results (%s) to server.." % gui.outfile))
                    try:
                        fd = open(gui.outfile, "rb")
                        fd.seek(0, 2)
                        size = fd.tell()
                        gui.log(_("%d bytes to send!" % size))
                        self.request.send(struct.pack("<I", size))
                        fd.seek(0, 0)
                        while 1:
                            buf = fd.read(16384)
                            if not buf:
                                break
                            self.request.send(buf)
                    except:
                        gui.log(_("Error: unable to open %s!" % gui.outfile))
                        self.request.send(struct.pack("<I", 0))
                elif cmd == COMMAND_BANDWIDTH:
                    gui.log(_("Testing bandwidth"))
                    try:
                        # download
                        toread = BANDWIDTH_BUFSIZE
                        while toread > 0:
                            data = self.request.recv(65536)
                            if not data:
                                gui.log(_("Error: no data received!"))
                                return
                            toread -= len(data)
                            print "Received %d, to go: %d" % (len(data), toread)
                        # upload
                        print "Now sending data"
                        tosend = BANDWIDTH_BUFSIZE
                        # temporary packet
                        packet = " " * 65536
                        while tosend > 0:
                            count = self.request.send(packet)
                            tosend -= count
                            print "Sent: %d, to go: %d" % (count, tosend)
                    except:
                        gui.log(_("Error performing bandwidth test: %s!") % sys.exc_value)

        self.socket_client = ReusableSocketServer(('', self.port), MessageHandler)
        while 1:
            try:
                self.socket_client.handle_request()
            except socket.timeout:
                print "Timeout caught!"
                continue
            except:
                print "Error handling client socket!"
                break

if __name__ == "__main__":
    if get_os() == "Linux":
        print "Rodando em Linux"
        commands = commands_linux
    else:
        print "Rodando em Windows"
        print "Adicionando caminho-padrao do Wireshark no PATH"
        # Vamos adicionar o que falta no PATH
        path = os.getenv("path")
        programfiles = os.getenv("ProgramFiles")
        path += ";%s\\Wireshark" % programfiles
        os.putenv("path", path)
        commands = commands_windows

    # Atualizando a lista de interfaces
    ifaces = list_ifaces()
    gtk.gdk.threads_init()
    print _("Starting GUI..")
    gui = trafdump("iface/client.glade")
    try:
        gtk.gdk.threads_enter()
        gui.log(_("\n\nIMPORTANT!!\nPlease select capturing interface to start the benchmark!!\n\n"))
        gtk.main()
        gtk.gdk.threads_leave()
    except:
        print "exiting.."
        sys.exit()
