""" All things that can block or lag the UI etc. """
import builtins
import os
import string
import subprocess
import threading
import time
import asyncio

import pymem
from pymem.ptypes import RemotePointer

from src import ui, thread
from src.logger import Logger
from src.network import network
from src.network.discord import Discord
from src.processing import storage, listener


class ProcessingThread(thread.Thread):
    """ The Processing Thread is for the processing and storage etc.
    """

    def __init__(self, references: dict):
        """ Initialize
        :param references: references
        """
        super().__init__(references, self.__class__.__name__, 0.1)
        self.references = references

        # Components
        self.storage = None
        self.gateway = None
        self.network = None
        self.listener = None
        self.discord = None

        # Add thread to references
        self.references.update({"ProcessingThread": self})

    def at_start(self):
        """ Gets called before the loop
        """
        Logger.log("ProcessingThread", add=True)

        # Create basic ui to be able to display events
        self.references["RootThread"].queue.append(
            {"cmd": "create_widgets", "params": [], "kwargs": {}})

        # Initialize storage
        self.storage = storage.Storage(self.references)

        # Initialize network
        self.network = network.Network(self.references)

        # Initialize gateway
        self.gateway = Gateway(self.references)

        # Not initialize listener, because its a thread

        # Initialize discord (rich presence) and event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.discord = Discord(self.references, loop=loop)

        # Finish UI content
        self.references["RootThread"].queue.append(
            {"cmd": "create_content", "params": [], "kwargs": {}})

    def at_end(self):
        """ Gets called after the loop
        """
        Logger.log("ProcessingThread", add=False)

    @thread.Thread.schedule(seconds=1)
    def update_storage_file(self):
        """ Update storage file
        """
        if self.storage.edited:
            self.storage.update_file()

            with self.storage.edited_lock:
                self.storage.edited = False

    @thread.Thread.schedule(seconds=1)
    def update_listener_keys(self):
        """ Update listener keys
        """
        if self.storage.listener_keys_edited:
            if self.listener:
                self.listener.register_keys()

            with self.storage.listener_keys_edited_lock:
                self.storage.listener_keys_edited = False

    @thread.Thread.schedule(seconds=15)
    def update_rich_presence(self):
        """ Update rich presence
        """
        # Features created
        if self.storage.features:
            # Feature enabled?
            if self.storage.features["3"]["enabled"]:
                if "3" in self.gateway.status and not self.gateway.status["3"]:
                    self.gateway.status["3"] = self.gateway.server_address_check(log=False)

                    # Update ui
                    self.references["RootThread"].queue.append(
                        {"cmd": "render_status", "params": [self.gateway.status], "kwargs": {}})

                    # Because it can be, that it wasn't updated once
                    if not self.gateway.status["3"]:
                        self.discord.update(bool(self.gateway.process_handle), None,
                                            self.gateway.current_mc_version)

                else:
                    # Can show server?
                    if self.storage.features["3"]["available"]:
                        self.discord.update(bool(self.gateway.process_handle), self.gateway.get_server(),
                                            self.gateway.current_mc_version)

                    else:
                        self.discord.update(bool(self.gateway.process_handle), None,
                                            self.gateway.current_mc_version)

    def start_button_handle(self, e):
        """ Starts or stops gateway and checks version
            cooldown of 10s
            Note: gets executed inside the processing thread
        :param e: tkinter event
        """
        root = self.references["Root"]
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
                    try:
                        # Get addresses
                        self.gateway.get_addresses()

                        # Set up and start listener
                        self.listener = listener.Listener(self.references)
                        self.listener.register_keys()
                        self.listener.start()

                        # Change start and tray button
                        self.references["SystemTray"].states["Enabled"] = True
                        self.references["SystemTray"].tray.update_menu()
                        root.start_button_var.set("■ Stop")

                        # Cooldown, need to copy
                        root.after(self.storage.get("settings")["attach_cooldown"],
                                   (lambda: button.configure(state="active")))
                        root.config(cursor="arrow")

                    except (pymem.exception.ProcessNotFound, pymem.exception.WinAPIError,
                            pymem.exception.CouldNotOpenProcess) as e:
                        Logger.log(f"Minecraft not found! {e}")
                        ui.queue_alert_message(self.references, "Minecraft not found!", warning=True)

                self.gateway.open_process_from_name("Minecraft.Windows.exe")
                self.gateway.status_check()
                Logger.log("Attached to Minecraft!")

                # Version check
                if not self.gateway.check_version() or not self.storage.get(
                        "features") or not self.storage.features.data:
                    Logger.log("New feature offsets are needed!")

                    # Fetch features, if it succeeded
                    if self.network.fetch_features(self.gateway.current_mc_version):
                        print("Create")
                        # Create if it isn't already created
                        self.references["RootThread"].queue.append(
                            {"cmd": "create_tab_features", "params": [self.storage.features], "kwargs": {},
                             "callback": lambda t: callback()})

                        return

                    # If something went wrong, error got displayed inside .fetch_features
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
                self.references["SystemTray"].states["Enabled"] = False
                self.references["SystemTray"].tray.update_menu()
                root.start_button_var.set("Start")

        except (pymem.exception.ProcessNotFound, pymem.exception.WinAPIError, pymem.exception.CouldNotOpenProcess) as e:
            Logger.log(f"Minecraft not found! {e}")
            ui.queue_alert_message(self.references, "Minecraft not found!", warning=True)

        # Cooldown
        root.after(self.storage.get("settings")["attach_cooldown"], (lambda: button.configure(state="active")))
        root.config(cursor="arrow")


class Gateway(pymem.Pymem):
    """ The 'Gateway' to mc, it handles the memory editing
    """

    def __init__(self, references: dict):
        """ Handles memory thanks to pymem, especially their discord helps a lot
        :param references: the references
        """
        super().__init__()
        self.references = references

        # Data components
        self.storage = references["Storage"]
        self.status = {
            "Connected": False,
            "Version": None,
        }

        # I just dont want to add strings every 20secs
        self.valid_domain_letters = set(string.ascii_letters + string.digits + "-.")
        self.fallback_server_address = None

        self.current_mc_version = None

        # Finish
        self.references.update({"Gateway": self})
        Logger.log("Gateway", add=True)

    def get_address(self, feature_id: str, *, log=True):
        """ Get one address
        :param feature_id: the id of the following feature
        :param log: if to log getting the address
        """
        feature = self.storage.features[feature_id]
        presets = self.storage.features.presets[feature_id]
        addresses = self.storage.features.addresses
        offset_outer = feature["offsets"]

        try:
            # If only one offset, so prepare list
            if presets["o_count"] == 1 or not isinstance(offset_outer, list):
                offset_outer = [offset_outer]

            addresses.update({feature_id: []})

            for i, offs in enumerate(offset_outer):
                # Find the address
                temp = RemotePointer(self.process_handle, self.process_base.lpBaseOfDll + offs[0])

                for offset in offs[1:-1]:
                    temp = RemotePointer(self.process_handle, temp.value + offset)

                # Add it
                addresses[feature_id].append(temp.value + offs[-1])

                if log:
                    Logger.log(
                        f"Found {i}. address for {feature['name']} [{hex(self.storage.features.addresses[feature_id][i])}]!",
                        add=True)

            status = True

        except pymem.exception.MemoryReadError:
            status = False

            if log:
                Logger.log(f"No address for {feature['name']}!", add=False)

        self.status.update({
            feature_id: status
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

                    # Get addresses for NoneTypes in feature settings values
                    # Only for listener compatible features
                    if self.storage.features.presets[_feature_id]["g"].listener:
                        for _key, _value in _feature_value["settings"].items():
                            if not _value or _value == " ":
                                _feature_value["settings"][_key] = (new_value := str(self.read_address(_feature_id)))
                                self.storage.features.tk_vars[_feature_id]["settings"][_key].set(new_value)

                    # Keep track
                    _done.add(_feature_id)

                else:
                    self.status.update({
                        _feature_id: None
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

    def read_address(self, feature_id: str, *, index: int = 0):
        """ Read a address based on its feature id
            Also decodes the new value
        :param feature_id: (str) id of the feature requested
        :param index: (int) which address should be used (1 feature can have multiple offsets)
        """
        if feature_id in self.storage.features.addresses:
            presets = self.storage.features.presets[feature_id]

            # Read and cast
            value = getattr(self, f"read_{presets['a_type']}")(self.storage.features.addresses[feature_id][index],
                                                               **(presets["a_args"] if "a_args" in presets else {}))

            # If it needs to be decoded
            if "s_decode" in presets:
                value = self.storage.features.presets[feature_id]["s_decode"](value)

            return value

    def write_address(self, feature_id: str, new, *, index: int = 0):
        """ Read a address based on its feature id,
            Also encodes the new value
        :param feature_id: (str) id of the feature requested
        :param new: the new value written
        :param index: (int) which address should be used (1 feature can have multiple offsets)
        """
        if feature_id in self.storage.features.addresses:
            presets = self.storage.features.presets[feature_id]

            # Cast into right type
            new = presets["s_type"](new)

            # If it needs to be encoded
            if "s_encode" in presets:
                new = self.storage.features.presets[feature_id]["s_encode"](new)

            # Write
            return getattr(self, f"write_{presets['a_type']}")(self.storage.features.addresses[feature_id][index], new,
                                                               **(presets["a_args"] if "a_args" in presets else {}))

    def is_domain(self, domain: str) -> bool:
        """ Tests if given domain is valid
        :param domain: (str) the domain
        """
        if "." not in domain or not set(domain).issubset(self.valid_domain_letters):
            return False

        return True

    def server_address_check(self, *, log=True):
        """ Checks if the addresses for the discord rich presence are available
        :param log: if to log messages
        """
        if "3" in self.storage.features.addresses:
            if not self.process_handle:
                return None

            self.get_server()  # Load fallback address if needed

            try:
                # Server port
                if self.read_int(self.storage.features.addresses["3"][1]) == 0:
                    return None

                # Server ip
                if self.fallback_server_address:
                    self.read_string(self.fallback_server_address, 253)

                elif (address := self.storage.features.addresses["3"][0]) == 0:
                    return None

                else:
                    self.read_string(address, 253)

            # Something happened, but is not 100% sure
            except (pymem.exception.MemoryReadError, UnicodeDecodeError, Exception, pymem.exception.ProcessError) as e:
                if log:
                    Logger.log(f"Discord is unavailable!", add=False)
                return False

            return True

        # No address loaded
        else:
            return None

    def get_fallback_server_address(self) -> int:
        """ Returns the fallback address for the connected server
        :returns: the address
        """
        a = self.read_uint(self.storage.features.addresses["3"][0])
        b = self.read_uint(self.storage.features.addresses["3"][0] + 4)

        return int(str(hex(b))[2:] + str(hex(a))[2:].zfill(8), 16)

    def get_server(self):
        """ Returns the currently connected server:port
        :returns: the server or None
        """
        if "3" in self.storage.features.addresses:
            try:
                port = self.read_int(self.storage.features.addresses["3"][1])

                # Zero means no server connected
                if port == 0:
                    return None

                # Use fallback address if needed
                if self.fallback_server_address:
                    address = self.fallback_server_address

                else:
                    address = self.storage.features.addresses["3"][0]

                # Means it wasn't connected the first time
                # try to get address again
                if address == 0:
                    self.get_address("3", log=False)
                    return None

                server = self.read_string(address, 253)

                # Check returned server domain
                if not server or not self.is_domain(server):
                    raise Exception

                else:
                    if port == 19132:
                        return server
                    else:
                        return f"{server}:{port}"

            # Need to read fallback value
            # Sometimes, even this fallback value failes, however, again, sometimes, by joining another server, it works again?
            except (pymem.exception.MemoryReadError, pymem.exception.WinAPIError, pymem.exception.ProcessError, UnicodeDecodeError, Exception):
                try:
                    # Reread port
                    port = self.read_int(self.storage.features.addresses["3"][1])

                    # If not done already, get fallback server address
                    if not self.fallback_server_address:
                        self.fallback_server_address = self.get_fallback_server_address()

                    server = self.read_string(self.fallback_server_address, 253)

                    if port == 19132:
                        return server

                    else:
                        return f"{server}:{port}"

                # Fallback failed, try to read orignial address again
                except (pymem.exception.MemoryReadError, pymem.exception.WinAPIError, pymem.exception.ProcessError, UnicodeDecodeError, UnicodeDecodeError, Exception):
                    # Logger.log("Server fallback address failed!")
                    self.fallback_server_address = None
                    self.get_address("3", log=False)
                    return None

        return None

    def status_check(self):
        """ Checks all sort of things for the status
        """
        # Check if minecraft is open
        self.status["Connected"] = bool(self.process_handle)

        # Check the minecraft version
        self.status["Version"] = bool(self.current_mc_version == self.storage.get("mc_version"))

        if self.storage.features:
            # Addresses
            for addr_id, addr_value in {_id: _addr for _id, sublist in self.storage.features.addresses.items() for _addr
                                        in sublist}.items():
                feature = self.storage.features[addr_id]

                try:
                    # Not enabled or not available
                    if not feature["enabled"] or not feature["available"] or not self.process_handle:
                        status = None

                    # Custom check
                    elif "a_status_check" in self.storage.features.presets[addr_id]:
                        status = self.storage.features.presets[addr_id]["a_status_check"](self)

                    # Else just try to read
                    else:
                        self.read_address(addr_id)

                        status = True

                    self.status[addr_id] = status

                except pymem.exception.MemoryReadError:
                    Logger.log(f"{feature['name']} is unavailable!", add=False)
                    self.status[addr_id] = False

        # Update ui
        self.references["RootThread"].queue.append(
            {"cmd": "render_status", "params": [self.status], "kwargs": {}})

    @staticmethod
    def get_mc_version() -> str:
        """ Get current mc version by using a powshell command
        """
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        version = subprocess.check_output(
            "powershell.exe Get-AppxPackage -name Microsoft.MinecraftUWP | select -expandproperty Version",
            stdin=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo)\
            .decode("utf8").rstrip()

        if version:
            Logger.log(f"Found MC Version '{version}'")

            return version

        else:
            return ""

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
