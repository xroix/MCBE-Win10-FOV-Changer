"""
Copyright 2020-2025 XroixHD

Main entry point that gets ported to an exe with pyinstaller
"""

from src import core


VERSION = "1.1.7-alpha"
DEBUG = False


if __name__ == '__main__':
    tray = core.SystemTray()
    tray.run()

