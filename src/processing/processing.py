""" All things that can block or lag the UI etc. """

import os
import threading
import time

import pymem
from pymem.ptypes import RemotePointer

from src import logger, ui
from src.network import network
from src.processing import storage, listener


class ProcessingThread(threading.Thread):
    """ The Processing Thread is for the processing and storage etc.
    """

    def __init__(self, interface: dict):
        """ Initialize
        :param interface: interface
        """
        super().__init__(name=self.__class__.__name__)
        self.interface = interface

        # Components
        self.storage = None
        self.gateway = None
        self.network = None

        # Queue
        self.running = False
        self.queue = []

        # Add thread to interface
        self.interface.update({"ProcessingThread": self})

    def run(self) -> None:
        """ Run method
        """
        logger.logDebug("ProcessingThread", add=True)

        # Create basic ui to be able to display events
        self.interface["RootThread"].queue.append(
            {"cmd": "createWidgets", "params": [True], "kwargs": {}})

        # Initialize storage
        self.storage = storage.Storage(self.interface)

        # Initialize network
        self.network = network.Network(self.interface)

        # Initialize gateway
        self.gateway = Gateway(self.interface)

        # Initialize listener
        # self.listener = listener.Listener(self.storage, self.gateway)
        # self.interface.update({"Listener": self.listener})

        # Authentication
        if self.network.isValidKey():
            # Finish UI content
            self.interface["RootThread"].queue.append(
                {"cmd": "createContent", "params": [], "kwargs": {}})

        else:
            # Ask user
            self.interface["RootThread"].queue.append(
                {"cmd": "createSetup", "params": [self.authenticationCallback.__name__], "kwargs": {}})

        # Loop
        self.running = True

        while self.running:
            if self.queue:
                task = self.queue.pop(0)

                # Execute task command
                return_value = getattr(self, task["cmd"])(*task["params"], **task["kwargs"])

                # Check if there is a callback
                if "callback" in task:
                    task["callback"](return_value)

            time.sleep(0.1)

        logger.logDebug("ProcessingThread", add=False)

    def authenticationCallback(self, license_key: str):
        """ Create the widget
        :param license_key: (str) the key
        """
        if (resp := self.network.authenticate(license_key))[0]:
            # Finish UI content
            self.interface["RootThread"].queue.append(
                {"cmd": "createContent", "params": [], "kwargs": {}})
            ui.queueAlertMessage(self.interface, "Successfully logged in!")

        # Invalid key
        else:
            ui.queueAlertMessage(self.interface, resp[1], warning=True)

    def startButtonHandle(self, e):
        """ Starts or stops gateway and checks version
            cooldown of 10s
        :param e: tkinter event
        """
        root = self.interface["Root"]
        button = root.start_button

        # Cooldown
        if button["state"] == "disabled":
            return

        button.configure(state="disabled")

        try:
            # Attach
            if (var := root.start_button_var).get() == "Start":
                self.gateway.open_process_from_name("Minecraft.Windows.exe")
                self.gateway.statusCheck()
                logger.logDebug("Attached to Minecraft!")

                # Version check
                if not self.gateway.checkVersion() or not self.storage.get("features") or not self.storage.features:
                    logger.logDebug("New feature offsets are needed!")

                    # Fetch features, if it succeeded
                    if self.network.fetchFeatures(self.gateway.current_mc_version):
                        # Create if it isn't already created
                        self.interface["RootThread"].queue.append(
                            {"cmd": "createTabFeature", "params": [self.storage.features], "kwargs": {}})

                    # If something went wrong
                    else:
                        self.gateway.close_process()
                        root.start_button_var.set("Start")
                        root.after(10, (lambda: button.configure(state="active")))

                        return

                # Get addresses
                if not self.storage.features.addresses:
                    self.gateway.getAddresses()

                # Change start button
                root.start_button_var.set("■ Stop")

            # Detach
            elif var.get() == "■ Stop":
                self.gateway.close_process()
                logger.logDebug("Detached from Minecraft!")

                # Change start button
                root.start_button_var.set("Start")

        except pymem.exception.ProcessNotFound:
            ui.queueAlertMessage(self.interface, "Minecraft not found!", warning=True)

        # Cooldown
        root.after(self.storage.get("settings")["start_cooldown"], (lambda: button.configure(state="active")))


class Gateway(pymem.Pymem):
    """ The 'Gateway' to mc, it handles the memory editing
    """

    def __init__(self, interface: dict):
        """ Handles memory thanks to pymem, especially their discord helps a lot
        :param interface: the interface
        """
        super().__init__()
        self.interface = interface

        # Data components
        self.storage = interface["Storage"]
        self.status = {
            "Connected": False,
            "Version": None,
        }

        self.current_mc_version = None

        # Finish
        self.interface.update({"Gateway": self})

    def getAddress(self, feature_id: str):
        """ Get one address
        :param feature_id: the id of the following feature
        """
        feature = self.storage.features[feature_id]
        offs = feature["offsets"]

        try:
            # Find the address
            temp = RemotePointer(self.process_handle, self.process_base.lpBaseOfDll + offs[0])

            for offset in offs[1:-1]:
                temp = RemotePointer(self.process_handle, temp.value + offset)

            self.storage.features.addresses.update({feature_id: temp.value + offs[-1]})
            status = True

            logger.logDebug(f"Found address for {feature['name']}!", add=True)

        except pymem.exception.MemoryReadError:
            status = False
            logger.logDebug(f"No address for {feature['name']}!", add=False)

        self.status.update({
            feature["name"]: status
        })

    def getAddresses(self):
        """ Get the features from the pointers
        """
        done = set()
        for feature_id, value in self.storage.features.data.items():
            if feature_id not in done:

                self.getAddress(feature_id)
                done.add(feature_id)

                # Update none values (use the current in-game value instead)
                self.storage.features.tk_vars

                if value["children"]:
                    for child_key in value["children"]:

                        self.getAddress(child_key)
                        done.add(child_key)

        self.statusCheck()

    def statusCheck(self):
        """ Checks all sort of things for the status
        """
        # Check if minecraft is open
        self.status["Connected"] = bool(self.process_handle)

        # Check the minecraft version
        self.status["Version"] = bool(self.current_mc_version == self.storage.get("mc_version"))

        # Addresses
        for addr_id, addr_value in self.storage.features.addresses.items():
            feature = self.storage.features[addr_id]

            try:
                getattr(self, f"read_{feature['value'][0]}")(addr_value)

            except pymem.exception.MemoryReadError:
                logger.logDebug(f"{feature['name']} is unavailable!", add=False)
                self.status[feature["name"]] = False

        # Update ui
        self.interface["RootThread"].queue.append(
            {"cmd": "renderStatus", "params": [self.status], "kwargs": {}})

    def getMCVersion(self) -> str:
        """ Get current mc version by checking the 'AppxManifest.xml' file
        """
        path = os.path.dirname(str(self.process_base.filename, "utf8"))

        # Test if it exists
        if os.path.exists((file_path := os.path.join(path, "AppxManifest.xml"))):
            # Parse it
            with open(file_path, "r") as f:
                version = f.read().split("<Identity")[1].split("Version=")[1].split('"')[1]

            logger.logDebug(f"Found MC Version '{version}'")

        else:
            return ""

        return version

    def checkVersion(self) -> bool:
        """ Check mc version if new features are required
        """
        self.current_mc_version = self.getMCVersion()
        saved_mc_version = self.storage.get("mc_version")

        # When they aren't equal, update needed
        if self.current_mc_version != saved_mc_version:
            logger.logDebug("Saved version doesn't match!")
            return False

        logger.logDebug("Saved version matches!")
        return True
