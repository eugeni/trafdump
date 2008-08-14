#!/usr/bin/python
"""
Traffic analysis client.
"""

import sys
import traceback
import time

import socket
import SocketServer
import fcntl
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

# configuracoes globais
commands = None
ifaces = list_ifaces()
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

    def network_selected(self, combobox):
        """A network interface was selected"""
        model = combobox.get_model()
        index = combobox.get_active()
        global iface_selected
        if index > 0:
            iface_selected = model[index][0]
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

class BcastSender(Thread):
    """Sends broadcast requests"""
    def __init__(self, port):
        Thread.__init__(self)
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('', 0))

    def run(self):
        """Starts threading loop"""
        print "Running!"
        while 1:
            # TODO: add timers to exit when required
            try:
                print " >> Sending broadcasting message.."
                self.sock.sendto("hello", ('255.255.255.255', self.port))
                time.sleep(1)
            except:
                traceback.print_exc()

class TrafClient(Thread):
    """Handles server messages"""
    def __init__(self, port):
        """Initializes listening thread"""
        Thread.__init__(self)
        self.port = port
        self.socket_client = None
        # Determina comandos a utilizar

    def run(self):
        """Starts listening to connections"""
        class MessageHandler(SocketServer.StreamRequestHandler):
            """Handles server messages"""
            def handle(self):
                """Handles incoming requests"""
                addr = self.client_address[0]
                print "Received request from %s" % addr
                msg = self.request.recv(1)
                cmd = struct.unpack('<b', msg)[0]
                if cmd == COMMAND_START_CAPTURE:
                    timestamp = self.request.recv(10)
                    descr = self.request.recv(32)
                    print "Starting capture to %s (%s)" % (descr, timestamp)
                    global iface_selected
                    if iface_selected not in ifaces:
                        print "!! ERROR!! Capturing interface not selecting, capturing to first available!"
                        iface_selected = ifaces.keys()[0]
                    iface_idx = ifaces[iface_selected]
                    print "Capturing on %s (%s)" % (iface_idx, iface_selected)
                    run_subprocess(
                            commands["capture"] % {"iface": iface_idx, "output": "%s.dump" % timestamp}
                            )
                elif cmd == COMMAND_STOP_CAPTURE:
                    run_subprocess(commands["stop"])
                    print "Stopping capture"
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
        commands = commands_windows

    gtk.gdk.threads_init()
    print _("Starting broadcasting service..")
    bcast = BcastSender(10000)
    bcast.start()
    print _("Starting listening service..")
    client = TrafClient(10000)
    client.start()
    print _("Starting GUI..")
    gui = trafdump("iface/client.glade")
    try:
        gtk.main()
    except:
        print "exiting.."
        sys.exit()
