""" The entrypoint - core methods and classes"""

import time

import pystray as ps
from PIL import Image

from src import logger
from src import ui
from src.processing import processing, storage


class SystemTray:
    """ The system stray, the main entry point.
    """

    def __init__(self):
        """ Initialize
        """
        super().__init__()

        # Interface, saves references of important objects
        # ** Add new references in its init (at the end to avoid not created attributes) ! **
        self.interface = {"SystemTray": self}

        # UI
        self.root_thread = ui.RootThread(self.interface)

        # Processing
        self.processing_thread = processing.ProcessingThread(self.interface)

        # Tray
        self.tray = None
        self.icon_image = Image.open("logo.ico")

        # For actions
        self.states = {
            "Enabled": False
        }
        self.actions = {
            "Open Settings": self.openRoot,
            "Exit": self.stopTray
        }

    def action(self, icon, item):
        """ Do a action based on item
        :param icon: the icon
        :param item: the item
        """
        self.actions[item.text]()

    def actionCheck(self, icon, item):
        """ Update check actions
        :param icon: the icon
        :param item: the item
        """
        self.states[item.text] = not item.checked

    def void(self, icon, item):
        """ Do nothing
        :param icon: the icon
        :param item: the item
        """
        pass

    def stopTray(self, *args, **kwargs):
        """ Stop the tray
        """
        self.tray.visible = False
        self.tray.stop()

    def openRoot(self):
        """ Open a window of the root
        """
        self.root_thread.root.deiconify()

    def run(self) -> None:
        """ Start everything because the tray controls most of the components
        """
        self.tray = ps.Icon("FOV Changer", icon=self.icon_image, title="FOV Changer", menu=ps.Menu(
            ps.MenuItem("FOV Changer", self.void, enabled=False),
            ps.Menu.SEPARATOR,
            ps.MenuItem("Open Settings", self.action),
            ps.MenuItem("Enabled", self.actionCheck, checked=lambda item: self.states["Enabled"]),
            ps.Menu.SEPARATOR,
            ps.MenuItem("Exit", self.action)
        ))

        # Start GUI
        self.root_thread.start()

        # Start Processing stuff
        self.processing_thread.start()

        # Start tray
        logger.logDebug("System Stray", add=True)
        self.tray.run()
        logger.logDebug("System Stray", add=False)

        self.onShutdown()

    def onShutdown(self):
        """ Will get executed when the tray stops
        """
        # Stop processing
        self.processing_thread.running = False

        # Stop the GUI
        self.root_thread.root.deiconify()
        self.root_thread.root.quit()
        self.root_thread.join()
