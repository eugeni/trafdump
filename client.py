#!/usr/bin/python
"""
Traffic analysis client.
"""

import sys
import traceback
import time

import socket
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
                print "Sending broadcasting message.."
                self.sock.sendto("hello", ('255.255.255.255', self.port))
                time.sleep(1)
            except:
                traceback.print_exc()

if __name__ == "__main__":
    gtk.gdk.threads_init()
    print _("Starting GUI..")
    bcast = BcastSender(10000)
    bcast.start()
    gui = trafdump("iface/client.glade")
    gtk.main()
