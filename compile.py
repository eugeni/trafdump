from distutils.core import setup

import py2exe
import glob

setup(
        console=['client.py', 'trafdump.py'],
        options = {
            'py2exe':
                {
                    "includes": "pango,cairo,pangocairo,atk,gobject,matplotlib.backends.backend_tkagg",
                },
                },
            data_files = [("iface", glob.glob("iface/*"))],
            zipfile = None,
        )
