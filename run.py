"""
Copyright 2024 XroixHD

Run file that gets ported to a exe with pyinstaller
"""

# For nuitka or pyinstaller
import pywintypes  # For fixing the 'DLL not found' error
import pkg_resources
import pystray._win32
import PIL._imaging

from src import core


VERSION = "1.1.7-alpha"
DEBUG = False


if __name__ == '__main__':
    tray = core.SystemTray()
    tray.run()

