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

import Queue

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
import thread
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
        self.ifaces = Queue.Queue()
        gobject.timeout_add(1000, self.find_ifaces)
        iface_finder = IfaceFinder(self)
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
        self.iface_selected = None
        self.outfile = None
        # Inicializa as threads
        self.bcast = BcastSender(LISTENPORT, self)
        self.client = TrafClient(LISTENPORT, self)
        self.log( _("Starting broadcasting service.."))
        self.bcast.start()
        self.log( _("Starting listening service.."))
        self.client.start()
        self.log(_("Looking for Wireshark interfaces.."))
        iface_finder.start()

    def find_ifaces(self):
        """Checks if there is any new wireshark interfaces"""
        if self.ifaces.empty():
            gobject.timeout_add(1000, self.find_ifaces)
            return
        # Something found
        ifaces = self.ifaces.get()
        if len(ifaces) < 1:
            # Wireshark probably not installed
            self.IfacesBox.set_sensitive(False)
            self.log(_("No wireshark network interface found!"))
            return
        self.log(_("%d wireshark capturing interfaces configured!") % len(ifaces))
        gui.log(_("Please select capturing interface to use Wireshark functionalty!!"))
        for z in ifaces.keys():
            self.IfacesBox.append_text(z)

    def network_selected(self, combobox):
        """A network interface was selected"""
        model = combobox.get_model()
        index = combobox.get_active()
        if index > 0:
            self.iface_selected = index
            gui.log( _("Capturing on %s") % model[index][0])
        else:
            self.iface_selected = None
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

    def log(self, text):
        """Logs a string"""
        #gtk.gdk.threads_enter()
        buffer = self.textview1.get_buffer()
        iter = buffer.get_end_iter()
        print text
        buffer.insert(iter, "%s: %s\n" % (time.asctime(), text))
        #gtk.gdk.threads_leave()

# {{{ BcastSender
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
                self.gui.log("Error sending broadcast message: %s" % sys.exc_value)
                traceback.print_exc()
                time.sleep(1)
# }}}

# {{{ McastListener
class McastListener(Thread):
    """Multicast listening thread"""
    def __init__(self):
        Thread.__init__(self)
        self.actions = Queue.Queue()
        self.messages = []
        self.lock = thread.allocate_lock()

    def get_log(self):
        """Returns the execution log"""
        self.lock.acquire()
        msgs = "\n".join(self.messages)
        return "# received msgs: %d msg_size: %d\n%s" % (len(self.messages), DATAGRAM_SIZE, msgs)
        self.lock.release()

    def stop(self):
        """Stops the execution"""
        self.actions.put(1)

    def run(self):
        """Keep listening for multicasting messages"""
        # Configura o socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', MCASTPORT))
        # configura para multicast
        mreq = struct.pack("4sl", socket.inet_aton(MCASTADDR), socket.INADDR_ANY)
        s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        # configura timeout para 1 segundo
        s.settimeout(1)
        # configura o mecanismo de captura de tempo
        if get_os() == "Windows":
            timefunc = time.clock
        else:
            timefunc = time.time
        last_ts = None
        while 1:
            if not self.actions.empty():
                print "Finishing multicast capture"
                s.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, mreq)
                s.close()
                return
            try:
                data = s.recv(DATAGRAM_SIZE + 1024)
                count = struct.unpack("<I", data[:struct.calcsize("<I")])[0]
                self.lock.acquire()
                curtime = timefunc()
                walltime = time.time()
                if not last_ts:
                    last_ts = curtime
                    timediff = 0
                else:
                    timediff = curtime - last_ts
                    last_ts = curtime
                self.messages.append("%d %f %f %f" % (count, timediff, curtime, walltime))
                self.lock.release()
            except socket.timeout:
                #print "Timeout!"
                pass
            except:
                print "Exception!"
                traceback.print_exc()
# }}}

# {{{ IfaceFinder
class IfaceFinder(Thread):
    """Wireshark interface finder. Separated into a separate thread to improve startup time"""
    def __init__(self, gui):
        Thread.__init__(self)
        self.gui = gui

    def run(self):
        """Locates wireshark interfaces"""
        ifaces = list_ifaces()
        self.gui.ifaces.put(ifaces)

# {{{ BcastListener
class BcastListener(Thread):
    """Broadcast listening thread"""
    def __init__(self):
        Thread.__init__(self)
        self.actions = Queue.Queue()
        self.messages = []
        self.lock = thread.allocate_lock()

    def get_log(self):
        """Returns the execution log"""
        self.lock.acquire()
        msgs = "\n".join(self.messages)
        return "# received msgs: %d msg_size: %d\n%s" % (len(self.messages), DATAGRAM_SIZE, msgs)
        self.lock.release()

    def stop(self):
        """Stops the execution"""
        self.actions.put(1)

    def run(self):
        """Keep listening for broadcasting messages"""
        # Configura o socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', BCASTPORT))
        # configura timeout para 1 segundo
        s.settimeout(1)
        # configura o mecanismo de captura de tempo
        if get_os() == "Windows":
            timefunc = time.clock
        else:
            timefunc = time.time
        last_ts = None
        while 1:
            if not self.actions.empty():
                print "Finishing broadcast capture"
                s.close()
                return
            try:
                data = s.recv(DATAGRAM_SIZE)
                count = struct.unpack("<I", data[:struct.calcsize("<I")])[0]
                self.lock.acquire()
                curtime = timefunc()
                walltime = time.time()
                if not last_ts:
                    last_ts = curtime
                    timediff = 0
                else:
                    timediff = curtime - last_ts
                    last_ts = curtime
                self.messages.append("%d %f %f %f" % (count, timediff, curtime, walltime))
                self.lock.release()
            except socket.timeout:
                #print "Timeout!"
                pass
            except:
                print "Exception!"
                traceback.print_exc()
# }}}

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
                    print "Capturing: %s" % descr
                    gui.log(_("Starting capture to %s") % (gui.outfile))
                    if not gui.iface_selected:
                        gui.log(_("\n!! ERROR!! Capturing not available!"))
                        return
                    print gui.iface_selected
                    print gui.ifaces
                    iface_idx = gui.iface_selected
                    # Primeiro, vamos parar as capturas antigas
                    run_subprocess(commands["stop"])
                    gui.log(_("Capturing on %s" % (iface_idx)))
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
                elif cmd == COMMAND_BANDWIDTH_TCP:
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
                        # upload
                        print "Now sending data"
                        tosend = BANDWIDTH_BUFSIZE
                        # temporary packet
                        packet = " " * 65536
                        while tosend > 0:
                            if tosend > 65536:
                                sendl = 65536
                            else:
                                sendl = tosend
                            count = self.request.send(packet[:sendl])
                            tosend -= count
                    except:
                        gui.log(_("Error performing bandwidth test: %s!") % sys.exc_value)
                elif cmd == COMMAND_BANDWIDTH_MULTICAST_START:
                    gui.log(_("Testing multicast bandwidth"))
                    gui.mcast_listener = McastListener()
                    gui.mcast_listener.start()
                    try:
                        pass
                    except:
                        gui.log(_("Error performing bandwidth test: %s!") % sys.exc_value)
                elif cmd == COMMAND_BANDWIDTH_MULTICAST_STOP:
                    gui.log(_("Finishing multicast bandwidth"))
                    gui.mcast_listener.stop()
                    log = gui.mcast_listener.get_log()
                    logsize = struct.pack("<I", len(log))
                    self.request.send(logsize)
                    self.request.send(log)
                    try:
                        pass
                    except:
                        gui.log(_("Error performing bandwidth test: %s!") % sys.exc_value)
                elif cmd == COMMAND_BANDWIDTH_BROADCAST_START:
                    gui.log(_("Testing broadcast bandwidth"))
                    gui.bcast_listener = BcastListener()
                    gui.bcast_listener.start()
                    try:
                        pass
                    except:
                        gui.log(_("Error performing bandwidth test: %s!") % sys.exc_value)
                elif cmd == COMMAND_BANDWIDTH_BROADCAST_STOP:
                    gui.log(_("Finishing broadcast bandwidth"))
                    gui.bcast_listener.stop()
                    log = gui.bcast_listener.get_log()
                    logsize = struct.pack("<I", len(log))
                    self.request.send(logsize)
                    self.request.send(log)
                    try:
                        pass
                    except:
                        gui.log(_("Error performing bandwidth test: %s!") % sys.exc_value)
                else:
                    print "Unknown command received!"

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

    # configura o timeout padrao para sockets
    socket.setdefaulttimeout(5)
    # Atualizando a lista de interfaces
    gtk.gdk.threads_init()

    print _("Starting GUI..")
    gui = trafdump("iface/client.glade")
    try:
        gtk.gdk.threads_enter()
        gtk.main()
        gtk.gdk.threads_leave()
    except:
        print "exiting.."
        sys.exit()
