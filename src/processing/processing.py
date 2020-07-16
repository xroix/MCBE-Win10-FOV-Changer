""" All things that can block or lag the UI etc. """
import builtins
import os
import threading
import time

import pymem
from pymem.ptypes import RemotePointer

from src import ui, exceptions
from src.logger import Logger
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
        self.listener = None

        # Queue
        self.running = False
        self.queue = []

        # Add thread to interface
        self.interface.update({"ProcessingThread": self})

    def run(self) -> None:
        """ Run method
        """
        try:
            Logger.log("ProcessingThread", add=True)

            # Create basic ui to be able to display events
            self.interface["RootThread"].queue.append(
                {"cmd": "create_widgets", "params": [], "kwargs": {}})

            # Initialize storage
            self.storage = storage.Storage(self.interface)

            # Initialize network
            self.network = network.Network(self.interface)

            # Initialize gateway
            self.gateway = Gateway(self.interface)

            # Not initialize listener, because its a thread

            # Authentication
            if self.network.is_valid_key():
                # Finish UI content
                self.interface["RootThread"].queue.append(
                    {"cmd": "create_content", "params": [], "kwargs": {}})

            else:
                # Ask user
                self.interface["RootThread"].queue.append(
                    {"cmd": "create_setup", "params": [self.authentication_callback.__name__], "kwargs": {}})

            # Loop
            self.running = True
            i = 0

            while self.running:
                if self.queue:
                    task = self.queue.pop(0)

                    # Execute task command
                    # Command ist attribute of ProcessingThread or a method?
                    if "attr" not in task or task["attr"]:
                        return_value = getattr(self, task["cmd"])(*task["params"], **task["kwargs"])

                    elif not task["attr"]:
                        return_value = task["cmd"](*task["params"], **task["kwargs"])

                    else:
                        return_value = None

                    # Check if there is a callback
                    if "callback" in task:
                        task["callback"](return_value)

                # Tasks for every 20 secs
                if i == 20:
                    i = 0

                    # Save update file if needed
                    if self.storage.edited:
                        self.storage.update_file()

                        with self.storage.edited_lock:
                            self.storage.edited = False

                    # Register listener keys new
                    if self.storage.listener_keys_edited:
                        if self.listener:
                            self.listener.register_keys()

                        with self.storage.listener_keys_edited_lock:
                            self.storage.listener_keys_edited = False

                else:
                    i += 1

                time.sleep(0.1)

            Logger.log("ProcessingThread", add=False)

        # If something happens, log it
        except Exception as e:
            exceptions.handle(self.interface)

    def authentication_callback(self, license_key: str):
        """ Create the widget
        :param license_key: (str) the key
        """
        if (resp := self.network.authenticate(license_key))[0]:
            # Finish UI content
            self.interface["RootThread"].queue.append(
                {"cmd": "create_content", "params": [], "kwargs": {}})
            Logger.log("Successfully logged in!")
            ui.queue_alert_message(self.interface, "Successfully logged in!")

        # Invalid key
        else:
            Logger.log(resp[1])
            ui.queue_alert_message(self.interface, resp[1], warning=True)

    def start_button_handle(self, e):
        """ Starts or stops gateway and checks version
            cooldown of 10s
            Note: gets executed inside the processing thread
        :param e: tkinter event
        """
        root = self.interface["Root"]
        button = root.start_button

        # Cooldown
        if button["state"] == "disabled":
            return

        button.configure(state="disabled")
        root.config(cursor="wait")

        try:
            # Attach
            if (var := root.start_button_var).get() == "Start":

                # Will get called at end
                def callback():
                    """ End of the start part, own method, so it can be invoked after the creation of features tab
                    """
                    # Get addresses
                    self.gateway.get_addresses()

                    # Set up and start listener
                    self.listener = listener.Listener(self.interface)
                    self.listener.register_keys()
                    self.listener.start()

                    # Change start and tray button
                    self.interface["SystemTray"].states["Enabled"] = True
                    self.interface["SystemTray"].tray.update_menu()
                    root.start_button_var.set("■ Stop")

                    # Cooldown, need to copy
                    root.after(self.storage.get("settings")["attach_cooldown"],
                               (lambda: button.configure(state="active")))
                    root.config(cursor="arrow")

                self.gateway.open_process_from_name("Minecraft.Windows.exe")
                self.gateway.status_check()
                Logger.log("Attached to Minecraft!")

                # Version check
                if not self.gateway.check_version() or not self.storage.get("features") or not self.storage.features.data:
                    Logger.log("New feature offsets are needed!")

                    # Fetch features, if it succeeded
                    if self.network.fetch_features(self.gateway.current_mc_version):

                        # Create if it isn't already created
                        self.interface["RootThread"].queue.append(
                            {"cmd": "create_tab_features", "params": [self.storage.features], "kwargs": {},
                             "callback": lambda t: callback()})

                        return

                    # If something went wrong
                    else:
                        self.gateway.close_process()
                        self.gateway.status_check()

                        root.start_button_var.set("Start")
                        root.after(10, (lambda: button.configure(state="active")))
                        root.config(cursor="arrow")

                        return

                # Do stuff
                callback()

            # Detach
            elif var.get() == "■ Stop":
                self.gateway.close_process()
                self.gateway.status_check()
                Logger.log("Detached from Minecraft!")

                # Stop listener
                self.listener.stop()

                # Change start button + tray's enabled button
                self.interface["SystemTray"].states["Enabled"] = False
                self.interface["SystemTray"].tray.update_menu()
                root.start_button_var.set("Start")

        except (pymem.exception.ProcessNotFound, pymem.exception.WinAPIError):
            Logger.log("Minecraft not found!")
            ui.queue_alert_message(self.interface, "Minecraft not found!", warning=True)

        # Cooldown
        root.after(self.storage.get("settings")["attach_cooldown"], (lambda: button.configure(state="active")))
        root.config(cursor="arrow")


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

    def get_address(self, feature_id: str):
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

            Logger.log(f"Found address for {feature['name']}!", add=True)

        except pymem.exception.MemoryReadError:
            status = False
            Logger.log(f"No address for {feature['name']}!", add=False)

        self.status.update({
            feature["name"]: status
        })

    def get_addresses(self):
        """ Get the features from the pointers
        """

        def inner(_done: set, _feature_id: str, _feature_value: dict):
            """ Handle a feature, separate method to avoid duplicates
            :param _done: (set) keeping track list
            :param _feature_id: (str) the id of the feature
            :param _feature_value: (dict) the value of the feature
            """
            # It should be the original + available
            if _feature_id not in _done:
                if _feature_value["available"]:
                    # Use the pointer
                    self.get_address(_feature_id)

                    # Get addresses for NoneTypes in feature value value
                    for i, _value in enumerate(_feature_value["value"]):
                        if not _value or _value == " ":
                            _feature_value["value"][i] = (new_value := str(self.read_address(_feature_id)))
                            self.storage.features.tk_vars[_feature_id]["value"][i].set(new_value)

                    # Keep track
                    _done.add(_feature_id)

                else:
                    self.status.update({
                        _feature_value["name"]: None
                    })

        done = set()
        for feature_id, value in self.storage.features.data.items():

            # Parse parent
            inner(done, feature_id, value)

            if value["children"]:
                for child_key in value["children"]:

                    # Parse child
                    inner(done, child_key, self.storage.features[child_key])

        # Finally, check all again and update storage file
        self.status_check()
        self.storage.update_file()

    def read_address(self, feature_id: str):
        """ Read a address based on its feature id
            Also decodes the new value
        :param feature_id: (str) id of the feature requested
        """
        if feature_id in self.storage.features.addresses:
            presets = self.storage.features.presets[feature_id]

            # Read and cast
            value = getattr(self, f"read_{presets['v_type']}")(self.storage.features.addresses[feature_id])

            # If it needs to be decoded
            if "v_decode" in presets:
                value = self.storage.features.presets[feature_id]["v_decode"](value)

            return value

    def write_address(self, feature_id: str, new):
        """ Read a address based on its feature id,
            Also encodes the new value
        :param feature_id: (str) id of the feature requested
        :param new: the new value written
        """
        if feature_id in self.storage.features.addresses:
            presets = self.storage.features.presets[feature_id]

            # Cast into right type
            new = getattr(builtins, presets["v_type"])(new)

            # If it needs to be encoded
            if "v_encode" in presets:
                new = self.storage.features.presets[feature_id]["v_encode"](new)

            # Write
            return getattr(self, f"write_{presets['v_type']}")(self.storage.features.addresses[feature_id], new)

    def status_check(self):
        """ Checks all sort of things for the status
        """
        # Check if minecraft is open
        self.status["Connected"] = bool(self.process_handle)

        # Check the minecraft version
        self.status["Version"] = bool(self.current_mc_version == self.storage.get("mc_version"))

        if self.storage.features:
            # Addresses
            for addr_id, addr_value in self.storage.features.addresses.items():
                feature = self.storage.features[addr_id]

                try:
                    if not feature["enabled"] or not feature["available"]:
                        self.status[feature["name"]] = None

                    else:
                        if self.process_handle:
                            self.read_address(addr_id)

                        self.status[feature["name"]] = True

                except pymem.exception.MemoryReadError:
                    Logger.log(f"{feature['name']} is unavailable!", add=False)
                    self.status[feature["name"]] = False

        # Update ui
        self.interface["RootThread"].queue.append(
            {"cmd": "render_status", "params": [self.status], "kwargs": {}})

    def get_mc_version(self) -> str:
        """ Get current mc version by checking the 'AppxManifest.xml' file
        """
        path = os.path.dirname(str(self.process_base.filename, "utf8"))

        # Test if it exists
        if os.path.exists((file_path := os.path.join(path, "AppxManifest.xml"))):
            # Parse it
            with open(file_path, "r") as f:
                version = f.read().split("<Identity")[1].split("Version=")[1].split('"')[1]

            Logger.log(f"Found MC Version '{version}'")

        else:
            return ""

        return version

    def check_version(self) -> bool:
        """ Check mc version if new features are required
        """
        self.current_mc_version = self.get_mc_version()
        saved_mc_version = self.storage.get("mc_version")

        # When they aren't equal, update needed
        if self.current_mc_version != saved_mc_version:
            Logger.log("Saved version doesn't match!")
            return False

        Logger.log("Saved version ist correct!")
        return True
