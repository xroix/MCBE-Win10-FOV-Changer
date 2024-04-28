import abc
import builtins
import json
import os
import sys
import threading
import tkinter as tk
import tkinter.ttk as ttk

from src import ui
from src.logger import Logger
from src.exceptions import MessageHandlingError


def find_file(name, *, meipass=False) -> str:
    """ Find filename, see: https://cx-freeze.readthedocs.io/en/latest/faq.html#using-data-files
        + https://stackoverflow.com/questions/7674790/bundling-data-files-with-pyinstaller-onefile
    :param name: file name / path
    :param meipass: (bool) try to get data from pyinstaller
    """
    # Pyinstaller data?
    if meipass:
        try:
            meipass_path = sys._MEIPASS

        except AttributeError:
            meipass_path = None

    else:
        meipass_path = None

    if meipass_path:
        directory = meipass_path
        name = os.path.basename(name)

    elif hasattr(sys, "frozen"):
        directory = os.path.dirname(sys.executable)
        name = os.path.basename(name)

    else:
        directory = os.path.dirname(sys.argv[0])

    # print(hasattr(sys, "frozen"))
    # print(directory, " <-> ", name)
    # print(os.path.abspath(name))

    return os.path.abspath(os.path.join(directory, name))


def find_dir(name):
    """ Find a directory
    :param name: the directory
    """
    if hasattr(sys, "frozen"):
        base_dir = os.path.dirname(sys.executable)

    else:
        base_dir = os.path.dirname(sys.argv[0])

    return os.path.join(base_dir, name)


class Group:
    """ Settings for a group of features
    """

    @property
    @abc.abstractmethod
    def listener(self) -> bool:
        """ Uses the listener for changing the features' addresses
        :return: (bool)
        """
        pass

    @property
    @abc.abstractmethod
    def edit_button(self) -> bool:
        """ If it should have a edit button and its top level
        :return: (bool)
        """
        pass

    @staticmethod
    @abc.abstractmethod
    def create_edit_button_widgets(manager, top: tk.Toplevel, feature_id: str, feature: dict, payload: dict):
        """ Method for creating the widgets inside the edit-button-top-level
            Note: enable .edit_button
        :param manager: (FeatureEditManager) the top level manager obj
        :param top: (TopLevel) the top level
        :param feature_id: (str) id of the feature
        :param feature: (dict) the dict associated to the feature
        :param payload: (dict) for storing tk_vars
        """
        pass


class ZoomGroup(Group):
    """ Groups zoom features (fov, sensitivity, hide hand)
    """
    listener = True
    edit_button = True

    @staticmethod
    def create_edit_button_widgets(manager, top: tk.Toplevel, feature_id: str, feature: dict, payload: dict):
        """ See Group
        """
        before = tk.StringVar()
        before.set(str(temp if (temp := feature["settings"]["before"]) is not None else ""))

        after = tk.StringVar()
        after.set(str(temp if (temp := feature["settings"]["after"]) is not None else ""))

        payload["settings"].update({"before": before, "after": after})

        # Before
        before_wrapper = tk.Frame(top, height=29, width=70)
        before_wrapper.place(relx=.3, rely=.3, anchor="center")
        before_wrapper.pack_propagate(0)
        ttk.Entry(before_wrapper, font=(manager.root.font, 12), justify="center",
                  textvariable=before) \
            .pack(fill="both")

        # Middle
        tk.Label(top, text="➞", font=(manager.root.font, 25), fg="#3A606E") \
            .place(relx=.5, rely=.3, anchor="center")

        # After
        after_wrapper = tk.Frame(top, height=29, width=70)
        after_wrapper.place(relx=.7, rely=.3, anchor="center")
        after_wrapper.pack_propagate(0)
        ttk.Entry(after_wrapper, font=(manager.root.font, 12), justify="center",
                  textvariable=after) \
            .pack(fill="both")

        # Save
        save_button_wrapper = tk.Frame(top, width=110, height=29)
        save_button_wrapper.pack_propagate(0)
        ttk.Button(save_button_wrapper, text="Save", takefocus=False,
                   command=lambda: manager.save(feature_id)).pack(fill="both")
        save_button_wrapper.place(relx=.5, rely=.7, anchor="center")


class DiscordGroup(Group):
    """ Groups the discord rich presence feauture
    """
    listener = False
    edit_button = True

    @staticmethod
    def create_edit_button_widgets(manager, top: tk.Toplevel, feature_id: str, feature: dict, payload: dict):
        """ See Group
            Uses no payload and custom save method for discord
        """
        show_server = tk.IntVar()
        show_server.set(temp if (temp := feature["settings"]["show_server"]) is not None else "")

        show_version = tk.IntVar()
        show_version.set(temp if (temp := feature["settings"]["show_version"]) is not None else "")

        payload["settings"].update({"show_server": show_server, "show_version": show_version})

        ttk.Checkbutton(top, text=f"   Show connected server?",
                        variable=show_server, cursor="hand2").pack(pady=17)

        ttk.Checkbutton(top, text=f"   Show minecraft version?",
                        variable=show_version, cursor="hand2").pack(pady=0)

        # Save
        save_button_wrapper = tk.Frame(top, width=110, height=29)
        save_button_wrapper.pack_propagate(0)
        ttk.Button(save_button_wrapper, text="Save", takefocus=False,
                   command=lambda: manager.save(feature_id)).pack(fill="both")
        save_button_wrapper.pack(pady=17)


class Features:
    """ Handles features so that they are available in many formats
        TODO be guilty, a redo is planned and wanted by myself
        TODO redo of the feature system, implement so, that versions get cached, in honor for my api xD
        TODO reminder: features folder containing {version}.json files
        TODO note that it can only be saved because it uses a reference of the original source
    """

    def __init__(self, references: dict):
        """ Initialize
        :param references: the references
        """
        self.references = references
        self.storage = references["Storage"]

        # Stores general data
        self.data = {}

        # Stores version specific data, todo make use of it
        self.offsets = {}

        # Stores the found addresses for the gateway
        self.addresses = {}

        # TkVars from ui
        self.tk_vars = {}

        # For quick access
        self.len = 0

        # Parsing the shorten keys from server response
        # and check if something is missing
        self.short_keys_table = {
            "a": "available",  # If it is available
            "o": "offsets"  # Offsets
        }

        # For some kind of security (not efficient) and to prevent the use of offsets for 'hacks' like air jump
        # hard code some things for the features
        self.presets = {
            "0": {  # FOV
                "g": ZoomGroup,
                "n": "FOV",  # Name
                "k": "v",  # Key
                "o_count": 1,  # Offsets count
                "a_type": "float",  # Type of address value, write out definition from pymem
                "s_type": float,  # Type of settings (saved)
                "s_default": {"before": None, "after": 30.0},  # Settings default value, used to determine type
                "s_check": lambda values: all(not x or (29 < float(x) < 111) for x in values),  # Check for all settings
                "s_decode": lambda old: round(old),  # Settings decode method for reading (encode for writing)
                "c": ["1", "2"]  # Children

            },
            "1": {  # Hide Hand
                "g": ZoomGroup,
                "n": "Hide Hand",
                "k": None,
                "o_count": 1,
                "a_type": "int",
                "s_type": int,
                "s_default": {"before": 0, "after": 1},
                "s_check": lambda values: all(not x or (-1 < int(x) < 2) for x in values),
                "c": []
            },
            "2": {  # Sensitivity, note middle (gui 50) = 0.5616388917, equation generated with https://mycurvefit.com/
                "g": ZoomGroup,
                "n": "Sensitivity",
                "k": None,
                "o_count": 1,
                "a_type": "float",
                "s_type": float,
                "s_default": {"before": None, "after": 16.0},
                "s_check": lambda values: all(not x or (0 <= float(x) <= 100) for x in values),
                "s_encode": lambda new: 6873.479 + (3.000883e-7 - 6873.479) / (1 + (new / 235581800) ** 0.6125547),
                "s_decode": lambda old: round(5331739 + (0.00002094196 - 5331739) / (1 + (old / 674.5356) ** 1.632673)),
                "c": []
            },
            "3": {
                "g": DiscordGroup,
                "n": "Discord",
                "o_count": 2,
                "a_type": "string",
                "a_status_check": lambda gateway: gateway.server_address_check(),  # Override for checking for a address in status check
                "s_type": bool,
                "s_default": {"show_server": True, "show_version": True},
                "c": []
            }
        }

    def __len__(self):
        """ Magic operator for length
        """
        return self.len

    def __getitem__(self, item) -> dict:
        """ Magic operator for getting a feature by id
        :param item: the feature id
        :returns: (dict) the feature value
        """
        return self.data[item]

    @property
    def for_json(self) -> dict:
        """ Gives features ready for json parser
        """
        return self.data

    @staticmethod
    def check_settings(features, feature_id: str, feature_value: dict, *, override: list = None) -> bool:
        """ Checks if the settings of a feature are correct, will translate values and change by reference
        :param features: (Features) the features object
        :param feature_id: (str) id of the specific feature
        :param feature_value: (dict) the specific feature
        :param override: (list) instead check this
        :returns: (bool) if succeed
        """
        presets = features.presets[feature_id]

        # # Return, it has no settings to check
        # if not presets["g"].has_settings:
        #     return True

        settings = feature_value["settings"] if not override else override

        try:
            # Check settings values
            # setting_type = type([x for x in presets["s_default"].values() if x is not None][0])
            temp = (presets["s_type"](setting_value) for setting_value in settings.values() if setting_value is not None)
            # Store setting_type for later use

            # Check if the values are in correct shape
            if "s_check" in presets and not presets["s_check"](list(settings.values())):
                raise ValueError()

            return True

        except (ValueError, AttributeError) as e:
            return False

    @classmethod
    def parse_features(cls, features, old_features: dict, *, shorten_keys=False, saved_features: dict = None) -> dict:
        """ Parses features
        :param features: (Features) the new features instance
        :param old_features: (dict) the response features unparsed
        :param shorten_keys: (bool) keys already parsed?
        :param saved_features: (dict) old saved features from last version etc
        :returns: (dict) the new features
        :raise MessageHandlingError: with a message
        """
        # Check for duplicates
        if len(old_features) != len(set(old_features)):
            raise MessageHandlingError("Duplicate feature ids found!")

        # No .items() for reference
        for feature_id in old_features.copy():
            feature_value = old_features[feature_id]

            # Not vanilla feature
            if feature_id not in features.presets:
                raise MessageHandlingError(f"Unknown feature id '{feature_id}'!")

            # Parse shorten keys, note: items makes a copy
            if shorten_keys:
                for old_key, new_key in features.short_keys_table.items():
                    if old_key in feature_value:

                        # Change key
                        feature_value[new_key] = feature_value.pop(old_key)

                    else:
                        raise MessageHandlingError(f"Key '{old_key}' is missing in feature {feature_id}!")

            # Preserve old saved preferences
            if saved_features:
                feature_value.update({
                    "settings": saved_features[feature_id]["settings"],
                    **({"key": saved_features[feature_id]["key"]} if features.presets[feature_id]["g"].listener else {}),
                    "enabled": saved_features[feature_id]["enabled"]
                })

            def set_default(key: str, default_key, *, override: bool = False):
                """ Add or updates a key if needed
                :param key: the key to change
                :param default_key: the key to access the presets
                :param override: if to use the default key as the new value
                """
                if key not in feature_value or (key in feature_value and not feature_value[key] and feature_value[key] is not False):  # or not feature_value[key]:
                    feature_value.update(
                        {key: default_key if override else features.presets[feature_id][default_key]})

            # Default values
            set_default("name", "n")
            set_default("enabled", True, override=True)

            if features.presets[feature_id]["g"].listener:
                set_default("key", "k")

            set_default("settings", "s_default")
            set_default("children", "c")

            # Only if feature is available for our version
            if feature_value["available"]:

                # Correct value type?
                if not cls.check_settings(features, feature_id, feature_value):
                    raise MessageHandlingError(f"Invalid settings for feature '{feature_id}'")

                # Correct number of offsets?
                if "offsets" in feature_value and 1 != features.presets[feature_id]["o_count"] != len(
                        feature_value["offsets"]):
                    raise MessageHandlingError(f"Invalid number of offsets for feature '{feature_id}'")

        return old_features

    @classmethod
    def from_server_response(cls, references: dict, response_features: dict, *, saved_features=None):
        """ Creates a feature object from the response features
        :param references: (dict) the references
        :param response_features: (dict) the dictionary from the server
        :param saved_features: (dict) old saved features from eg old version
        :returns: (Features)
        """
        new_features = Features(references)

        # Parse
        new_features.data = cls.parse_features(new_features, response_features, shorten_keys=True,
                                               saved_features=saved_features)
        new_features.len = len(new_features.data)

        return new_features

    @classmethod
    def from_storage_file(cls, references: dict, storage_features: dict):
        """ Creates a feature object from the storage files data
        :param references: (dict) the references
        :param storage_features: (dict) the dictionary from the storage
        :returns: (Features)
        """
        new_features = Features(references)

        # Parse
        new_features.data = cls.parse_features(new_features, storage_features, shorten_keys=False)
        new_features.len = len(new_features.data)

        return new_features


class Settings:
    """ Handles settings
    """

    def __init__(self, references: dict):
        """ Initialize
        :param references: the references
        """
        self.references = references

        # Settings
        self.data = {}

        # Tk vars for settings frame
        self.tk_vars = {}

        self.presets = {
            "start_minimized": {
                "d": False,  # Default
                "n": "Start minimized?",  # Displayed name
            },
            "auto_attach": {
                "d": False,
                "n": "Auto attach?"
            },
            "attach_cooldown": {
                "d": 2000,
                "n": "Attach cooldown"
            },
            "fov_smooth": {
                "d": True,
                "n": "FOV smooth change?"
            },
            "fov_smooth_duration": {
                "d": 100,
                "n": "FOV smoothing duration (millisecond)"
            },
            "fov_smooth_steps": {
                "d": 200,
                "n": "FOV smoothing steps\n (high steps might be laggier)"
            },
            "exit_all": {
                "d": True,
                "n": "Exit all"
            }
            # "clear_features": {  # TODO part of the Features rewrite
            #     "d": lambda e: print("test"),  # If method, it is a "action button"
            #     "n": "Clear stored features"
            # }
        }

    def __getitem__(self, item) -> dict:
        """ Magic operator for getting a setting by name
        :param item: the setting name / id
        :returns: (dict) the setting value
        """
        return self.data[item]

    @property
    def for_json(self) -> dict:
        """ Gives settings ready for json parser
        """
        return {x: y for x, y in self.data.items() if not callable(y)}  # Only non action ones

    @classmethod
    def from_storage_file(cls, references: dict, storage):
        """ Creates a settings object from the storage file's data
        :param references: (dict) the references
        :param storage: (Storage) the storage obj
        :raises FileNotFoundError: on error
        :returns: (Features)
        """
        new_settings = Settings(references)

        presets = new_settings.presets.copy()

        # Check settings
        for setting, value in storage.get("settings").items():
            if setting in presets and isinstance(value, type(presets[setting]["d"])):
                del presets[setting]

                # Add it
                new_settings.data.update({setting: value})

            # Wrong setting
            else:
                ui.queue_quit_message(references, f"Invalid storage file! Setting '{setting}' is a wrong type or unknown!",
                                      "Fatal Error")

                return None

        # Add missing settings
        for remaining_preset, value in presets.items():
            new_settings.data.update({remaining_preset: value["d"]})

        return new_settings


class Storage:
    """ Interface to the storage.json file
    """

    STORAGE_PATH = find_file("res\\storage.json")
    FEATURES_DIR = find_file("features\\")

    STORAGE_TEMPLATE = {
        "mc_version": "",
        "api": "https://fov.xroix.me/api/",
        "features_help_url": "https://fov.xroix.me/docs/features#{}",
        "settings_help_url": "https://fov.xroix.me/docs/settings#{}",
        "features": {

        },
        "settings": {
        }
    }

    def __init__(self, references):
        """ Initialize
        :param references: the references
        """
        self.references = references

        # Stored
        self.data = None
        self.features = None
        self.settings = None

        # If the storage was changed frequently by a process
        self.edited = False
        self.edited_lock = threading.Lock()

        # If the listener keys need to be updated
        self.listener_keys_edited = False
        self.listener_keys_edited_lock = threading.Lock()

        # If data can be already saved
        self.ready = False

        # Load STORAGE_PATH file
        try:
            with open(self.STORAGE_PATH, "a+") as f:
                # Using a+ instead of w+ because it doesn't truncate
                f.seek(0)

                # If is written read, else write default
                if f.read() != "":
                    f.seek(0)
                    self.data = json.load(f)

                    # Validate
                    if not self.validate(self.data, self.STORAGE_TEMPLATE):
                        raise FileNotFoundError

                else:
                    f.seek(0)
                    json.dump(self.STORAGE_TEMPLATE, f, indent=4)
                    self.data = self.STORAGE_TEMPLATE

        except (json.JSONDecodeError, FileNotFoundError):
            ui.queue_quit_message(self.references, "Invalid storage file! Please correct or delete it!", "Fatal Error")

            # Add to the references
            self.references.update({"Storage": self})

            return

        # Add to the references
        self.references.update({"Storage": self})

        # Load settings
        self.settings = Settings.from_storage_file(self.references, self)
        self.set("settings", self.settings.for_json)

        # Load features
        if self.data and self.data["features"]:
            try:
                self.features = Features.from_storage_file(self.references, self.data["features"])
                Logger.log("Stored features were loaded!")

            except MessageHandlingError as e:
                ui.queue_quit_message(self.references, f"Invalid storage file! {e.message}", "Fatal Error")
                return

        # Settings: Start minimized
        if self.settings["start_minimized"]:
            self.references["RootThread"].queue.append(
                {"cmd": "hide", "params": [], "kwargs": {"not_exit_all": True}, "wait_for_render": True})

        # Settings: Auto start
        if self.settings["auto_attach"]:
            self.references["RootThread"].queue.append(
                {"cmd": lambda: self.references["ProcessingThread"].queue.append(
                    {"cmd": "start_button_handle", "params": [None], "kwargs": {}}
                ), "params": [], "kwargs": {}, "wait_for_render": True})

        self.ready = True
        Logger.log("Storage", add=True)

    def validate(self, given: dict, check: dict) -> bool:
        """ Validate the storage file (recursive)
        :param given: (dict) which is user entered
        :param check: (dict) the template to whom check from
        :returns: (bool) succeeded?
        """
        for key, value in check.items():
            if key not in given:
                return False

            if isinstance(value, dict):
                if not self.validate(given[key], check[key]):
                    return False

        return True

    def set(self, name: str, value):
        """ Setter
        :param name: the name
        :param value: the value
        """
        self.data[name] = value

    def get(self, name: str):
        """ Getter
        :param name: the name
        """
        return self.data[name]

    def update_file(self):
        """ Update file content
        """
        if self.data and self.ready:
            # Save settings
            if self.settings:
                self.set("settings", self.settings.for_json)

            if self.features:
                self.set("features", self.features.for_json)

            with open(self.STORAGE_PATH, "w+") as f:
                f.seek(0)
                json.dump(self.data, f, indent=4)
