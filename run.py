"""
Copyright 2020 XroixHD

REQUIREMENTS: pymem, pynput, colorama, requests

CREDITS: Thanks to pymem's discord, they helped a lot

CHANGELOG:
    1.0.2: Added custom mc version support

"""
import pywintypes  # For fixing the 'DLL not found' error

from src import core

VERSION = "1.2.0"

if __name__ == '__main__':
    tray = core.SystemTray()
    tray.run()

