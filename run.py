"""
Copyright 2020 XroixHD

Main entry point that gets ported to an exe with pyinstaller
"""

# For nuitka or pyinstaller
import pywintypes  # For fixing the 'DLL not found' error
import pkg_resources
import pystray._win32
import PIL._imaging

from src import core


VERSION = "1.1.6-alpha"
DEBUG = False


if __name__ == '__main__':
    tray = core.SystemTray()
    tray.run()

