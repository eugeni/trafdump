#!/usr/bin/python
"""
Teacher GUI using GLADE
"""

import sys
import traceback

import os
import logging
import gtk
import gtk.glade
import pygtk

import gettext
import __builtin__
__builtin__._ = gettext.gettext

MACHINES_X=8
MACHINES_Y=8

class gui_teacher:
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

        # Main menu entries
        self.mainmenu_dict = [
                    {
                        "id": "home",
                        "text":_("Main"),
                        "img_normal": "home.png",
                        "img_active": "home.png",
                        "color_normal": gtk.gdk.color_parse("#99BFEA"),
                        "color_active": gtk.gdk.color_parse("#FFBBFF")
                    },
                    {
                        "id": "wifi_status",
                        "text": _("Wi-Fi Status"),
                        "img_normal": "wifi_status.png",
                        "img_active": "wifi_status_active.png",
                        "color_normal": gtk.gdk.color_parse("#99BFEA"),
                        "color_active": gtk.gdk.color_parse("#FFBBFF")
                    },
                    {
                        "id": "througput",
                        "text": _("Network Status"),
                        "img_normal": "network_status.png",
                        "img_active": "network_status_active.png",
                        "color_normal": gtk.gdk.color_parse("#99BFEA"),
                        "color_active": gtk.gdk.color_parse("#FFBBFF")
                    },
                    {
                        "id": "help",
                        "text": _("Help"),
                        "img_normal": "help.png",
                        "img_active": "help_active.png",
                        "color_normal": gtk.gdk.color_parse("#99BFEA"),
                        "color_active": gtk.gdk.color_parse("#FFBBFF")
                    },
                    {
                        "id": "about",
                        "text": _("About"),
                        "img_normal": "about.png",
                        "img_active": "about_active.png",
                        "color_normal": gtk.gdk.color_parse("#99BFEA"),
                        "color_active": gtk.gdk.color_parse("#FFBBFF")
                    }
                ]

        self.topmenu_dict = {}

        # tooltips
        self.tooltip = gtk.Tooltips()

        # Constroi a interface
        self.build_iface()

        # Constroi as maquinas
        self.machine_layout = [None] * MACHINES_X
        for x in range(0, MACHINES_X):
            self.machine_layout[x] = [None] * MACHINES_Y
        self.build_machines()

    def put_machine(self, machine):
        """Puts a client machine in an empty spot"""
        for y in range(0, MACHINES_Y):
            for x in range(0, MACHINES_X):
                if not self.machine_layout[x][y]:
                    self.machine_layout[x][y] = machine
                    self.MachineLayout.put(machine, x * 70, y * 80)
                    machine.machine_x = x
                    machine.machine_y = y
                    return
        #bluelab_config.error("Not enough layout space to add a machine!")

    def build_machines(self):
        """Builds client machines"""
        for z in range(0, 90):
            button = self.mkmachine("Machine %d" % z)
            self.put_machine(button)
        self.MachineLayout.show_all()


    def build_menu_home(self):
        """Builds initial BlueLab menu"""
        box = gtk.VBox(homogeneous=False)
        label = gtk.Label(_("Network status:"))
        box.pack_start(label, expand=False)

        # Menu
        #box.pack_start(
        #        self.mkbutton("turn_on.png", "turn_on.png", _("Turn on student machines"), self.action_turnon),
        #        expand = False
        #        )
        return box

    def build_menu_send_message(self):
        """Builds send message menu"""
        box = gtk.VBox(homogeneous = False)
        box2 = gtk.HBox(homogeneous = False, spacing=15)
        label = gtk.Label(_("Enter your message to send to all students"))
        msg_input = gtk.Entry()
        button = gtk.Button(_("Send!"))
        button.connect('clicked', self.cb_send_message, msg_input)
        box.pack_start(label, expand=False)
        box.pack_start(box2, expand=False)
        box2.pack_start(msg_input)
        box2.pack_start(button, expand=False)
        return box

    def cb_send_message(self, widget, data):
        """Sends a message to students"""
        print widget
        print data.get_text()

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
        button.connect('clicked', self.cb_machine, box)
        box.pack_start(button, expand=False)

        label = gtk.Label(_("name"))
        label.set_use_markup(True)
        label.set_markup("<small>%s</small>" % name)
        box.pack_start(label, expand=False)

        self.tooltip.set_tip(box, name)
        box.set_size_request(52, 52)

        # Sets private variables
        box.machine = name
        box.button = button
        box.label = label
        return box

    def cb_machine(self, widget, machine):
        """Callback when clicked on a client machine"""
        for x in self.machine_layout:
            for y in x:
                if y == machine:
                    # changes icon
                    img = y.button.get_image()
                    if not img:
                        break
                    if img == y.button.img_on:
                        y.button.set_image(y.button.img_off)
                    else:
                        y.button.set_image(y.button.img_on)
                    break

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

    def build_iface(self):
        """Builds main iface"""
        # Muda o background
        self.MainWindow.modify_bg(gtk.STATE_NORMAL, self.color_background)
        self.MachineLayout.modify_bg(gtk.STATE_NORMAL, self.color_background)

        # Cria o menu principal
        menu = self.MenuHBox

        # Build the menu
#        for id, img, img2, text, action in self.mainmenu_dict:
        for curmenu in self.mainmenu_dict:
            id = curmenu["id"]
            text = curmenu["text"]
            img = curmenu["img_normal"]
            img2 = curmenu["img_active"]
            color_normal = curmenu["color_normal"]
            color_active = curmenu["color_active"]

            # determina callback
            if hasattr(self, "action_%s" % id):
                action = getattr(self, "action_%s" % id)
            else:
                action = None

            button = self.mkbutton(img, img2, text, action, color_normal, color_active)
            # Controi o menu lateral
            menu.add(button)
            # Controi o menu superior
            builder = "build_menu_%s" % id
            method = getattr(self, builder)
            curpage = None
            if method:
                #bluelab_config.debug("Building menu for %s" % id)
                curpage = method()
            else:
                # Just create an empty frame
                #bluelab_config.debug("Building EMPTY menu for %s" % id)
                curpage = gtk.VBox()
            curpage.show_all()
            self.CommandHBox.append_page(curpage)
            self.topmenu_dict[id] = curpage
        self.CommandHBox.set_current_page(0)

    def show_menu(self, menuname):
        """Shows a menu for a page"""
        print "Trying to show %s" % menuname
        try:
            id = self.topmenu_dict[menuname]
            self.CommandHBox.set_current_page(self.CommandHBox.page_num(id))
        except:
            pass

    def action_turnon(self, widget, data):
        """Turns on student machines"""
        pass

    def action_home(self, widget, data):
        """Shows initial bluelab screen"""
        self.show_menu("home")

    def action_share_screen(self, widget, data):
        """Start screen sharing"""
        print "Starting screen sharing.."
        self.show_menu("share_screen")

    def action_request_attention(self, widget, data):
        """Request student attention"""
        self.show_menu("request_attention")

    def action_view_students_screen(self, widget, data):
        """Views student screen"""
        self.show_menu("view_students")

    def action_send_message(self, widget, data):
        """Sends a message to students"""
        self.show_menu("send_message")

    def action_send_file(self, widget, data):
        """Sends file to students"""
        pass

    def action_open_browser(self, widget, data):
        """Opens a browsers on student machines"""
        pass

    def action_open_application(self, widget, data):
        """Starts an application on student machines"""
        pass

    def action_lab_controls(self, widget, data):
        """Opens lab control screen"""
        pass

    def share_screen(self, widget, data):
        """Start screen sharing"""
        pass

    def share_screen(self, widget, data):
        """Start screen sharing"""
        pass

if __name__ == "__main__":
    print _("Starting Teacher GUI..")
    gui = gui_teacher("iface/wifimon.glade")
    gtk.main()
