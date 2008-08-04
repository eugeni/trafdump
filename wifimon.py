#!/usr/bin/python
"""
Teacher GUI using GLADE
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

import gettext
import __builtin__
__builtin__._ = gettext.gettext

# TODO: unfinished
# def wifi_params(iface):
#     """Returns wifi configuration parameters"""
#     ifacename = struct.pack('256s', iface)
#     s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#     wname = fcntl.ioctl(s.fileno(), 0x8B01, ifacename) # SIOCGIWNAME
#     wfreq = fcntl.ioctl(s.fileno(), 0x8B05, ifacename) # SIOCGIWFREQ
#     wessid = ""#fcntl.ioctl(s.fileno(), 0x8B1B, ifacename) # SIOCGIWESSID
#     wmode = ""#fcntl.ioctl(s.fileno(), 0x8B06, ifacename) # SIOCGIWMODE
#     wap = fcntl.ioctl(s.fileno(), 0x8B15, ifacename) # SIOCGIWAP
#     wrate = fcntl.ioctl(s.fileno(), 0x8B21, ifacename) # SIOCGIWRATE
#     return wname, wfreq, wessid, wmode, wap, wrate

def wifi_status():
    """Return current wifi link status"""
    data = open("/proc/net/wireless").readlines()[2].strip()
    iface, params = data.split(":", 1)
    # todo: REGEXP parsing
    fields = params.split()
    link = fields[1]
    level = fields[2]
    noise = fields[3]
    return iface, link, level, noise

class wifimon:
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

        # Muda o background
        self.MainWindow.modify_bg(gtk.STATE_NORMAL, self.color_background)
        self.MachineLayout.modify_bg(gtk.STATE_NORMAL, self.color_background)

        # Constroi as maquinas
        self.build_machines()

        # Configura os botoes
        self.QuitButton.connect('clicked', self.on_MainWindow_destroy)
        self.SaveButton.connect('clicked', self.save_results)

        # Configura o timer
        gobject.timeout_add(1000, self.monitor)

    def monitor(self):
        """Monitors WIFI status"""
        iface, link, level, noise = wifi_status()
        self.StatusLabel.set_markup("<b>Link:</b> %s, <b>Signal:</b> %s, <b>Noise:</b> %s" % (link, level, noise))
        gobject.timeout_add(1000, self.monitor)

    def save_results(self, widget):
        """Saves results"""
        print "Salvando!"
        for z in self.machines:
            print z.wifi

    def build_machines(self):
        """Builds client machines"""
        # cria 4 maquinas nos cantos
        machines_coord = [
                (0, 0, _("Top left corner")),
                (300, 0, _("Top right corner")),
                (0, 200, _("Bottom left corner")),
                (300, 200, _("Bottom right corner"))
                ]
        self.machines = []
        for x, y, text in machines_coord:
            machine = self.mkmachine(text, status="offline")
            machine.button.connect('clicked', self.cb_machine, machine)
            #self.machine_layout[x][y] = machine
            self.MachineLayout.put(machine, x, y)
            self.machines.append(machine)
        self.MachineLayout.show_all()


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
            self.selected_machines += 1
            if self.selected_machines > 3:
                self.SaveButton.set_sensitive(True)

        # muda o texto
        iface, link, level, noise = wifi_status()
        machine.wifi = link, level, noise
        machine.label.set_markup("Link: %s\nSignal: %s\nNoise: %s" % (link, level, noise))

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


if __name__ == "__main__":
    iface, link, level, noise = wifi_status()
    print _("Starting GUI..")
    gui = wifimon("iface/wifimon.glade")
    gtk.main()
