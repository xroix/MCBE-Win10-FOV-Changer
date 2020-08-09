"""
Copyright 2020 XroixHD

Run file that gets ported to a exe with pyinstaller
Note: use '--hidden-imports kg_resources.py2_warn' for some reason
"""

import pywintypes  # For fixing the 'DLL not found' error

from src import core


VERSION = "1.1.3"
DEBUG = False


if __name__ == '__main__':
    tray = core.SystemTray()
    tray.run()

