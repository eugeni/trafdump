from distutils.core import setup

import py2exe
import glob

setup(
        windows=['client.py', 'trafdump.py'],
        options = {
            'py2exe':
                {
                    "includes": "pango,cairo,pangocairo,atk,gobject",
                },
                },
            data_files = [("iface", glob.glob("iface/*"))],
            zipfile = None,
        )
