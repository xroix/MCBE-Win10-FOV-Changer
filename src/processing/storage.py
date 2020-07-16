import builtins
import json
import os
import sys
import threading

from src import ui
from src.logger import Logger
from src.exceptions import MessageHandlingError


def find_file(name, *, meipass=False):
    """ Find filename, see: https://cx-freeze.readthedocs.io/en/latest/faq.html#using-data-files
        + https://stackoverflow.com/questions/7674790/bundling-data-files-with-pyinstaller-onefile
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

    return os.path.join(directory, name)


class Features:
    """ Handles features so that they are available in many formats
    """

    def __init__(self, interface: dict):
        """ Initialize
        :param interface: the interface
        """
        self.interface = interface
        self.storage = interface["Storage"]

        # Features
        self.data = {}

        # Stores the found addresses for the gateway
        self.addresses = {}

        # TkVars from ui
        self.tk_vars = {}

        # For quick access
        self.len = 0

        # Parsing the shorten keys from server response
        # and check if something is missing
        self.hash_table = {
            "a": "available",  # If it is available
            "o": "offsets"  # Offsets
        }

        # For some kind of security (not efficient) and to prevent the use of offsets for 'hacks' like air jump
        # hard code some things for the features
        self.presets = {
            "0": {  # FOV
                "n": "FOV",
                "k": "v",
                "v_type": "float",
                "v_default": [None, "30"],
                "v_check": lambda values: all(not x or (29 < float(x) < 111) for x in values),
                "v_decode": lambda new: round(new),
                "c": ["1", "2"]

            },
            "1": {  # Hide Hand
                "n": "Hide Hand",
                "k": None,
                "v_type": "int",
                "v_default": ["0", "1"],
                "v_check": lambda values: all(not x or (-1 < int(x) < 2) for x in values),
                "c": []
            },
            "2": {  # Sensitivity, note middle (gui 50) = 0.5616388917, equation generated with https://mycurvefit.com/
                "n": "Sensitivity",
                "k": None,
                "v_type": "float",
                "v_default": [None, "1"],
                "v_check": lambda values: all(not x or (0 <= float(x) <= 100) for x in values),
                "v_encode": lambda old: 6873.479 + (3.000883e-7 - 6873.479)/(1 + (old/235581800)**0.6125547),
                "v_decode": lambda new: round(5331739 + (0.00002094196 - 5331739)/(1 + (new/674.5356)**1.632673)),
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
    def check_value(features, feature_id: str, feature_value: dict, *, override_value: list = None) -> bool:
        """ Checks if the value attribute of a feature is correct, will translate values and change by reference
        :param features: (Features) the features object
        :param feature_id: (str) id of the specific feature
        :param feature_value: (dict) the specific feature
        :param override_value: (list) new values
        :returns: (bool) if succeed
        """
        values = feature_value["value"] if not override_value else override_value
        presets = features.presets[feature_id]

        try:
            # Check value type
            temp = (getattr(builtins, presets["v_type"])(value) for value in values)

            # Check if the values are in correct shape
            if not presets["v_check"](values):
                raise ValueError()

            return True

        except (ValueError, AttributeError):
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
                for old_key, new_key in features.hash_table.items():
                    if old_key in feature_value:

                        # Change key
                        feature_value[new_key] = feature_value.pop(old_key)

                    else:
                        raise MessageHandlingError(f"Key '{old_key}' is missing in feature {feature_id}!")

            # Preserve old saved preferences
            if saved_features:
                feature_value.update({
                    "value": saved_features[feature_id]["value"],
                    "key": saved_features[feature_id]["key"],
                    "enabled": saved_features[feature_id]["enabled"]
                })

            def set_default(key: str, default_key, *, override: bool = False):
                """ Add or updates a key if needed
                :param key: the key to change
                :param default_key: the key to access the presets
                :param override: if to use the default key as the new value
                """
                if key not in feature_value or not feature_value[key]:
                    feature_value.update(
                        {key: override if override else features.presets[feature_id][default_key]})

            # Default values
            set_default("name", "n")
            set_default("enabled", True, override=True)
            set_default("key", "k")
            set_default("value", "v_default")
            set_default("children", "c")

            # Hard coded "security" checks
            # only if feature is available for our version
            if feature_value["available"]:

                # Correct value type?
                if not cls.check_value(features, feature_id, feature_value):
                    raise MessageHandlingError(f"Invalid value type for feature '{feature_id}'")

        return old_features

    @classmethod
    def from_server_response(cls, interface: dict, response_features: dict, *, saved_features=None):
        """ Creates a feature object from the response features
        :param interface: (dict) the interface
        :param response_features: (dict) the dictionary from the server
        :param saved_features: (dict) old saved features from eg old version
        :returns: (Features)
        """
        new_features = Features(interface)

        # Parse
        new_features.data = cls.parse_features(new_features, response_features, shorten_keys=True, saved_features=saved_features)
        new_features.len = len(new_features.data)

        return new_features

    @classmethod
    def from_storage_file(cls, interface: dict, storage_features: dict):
        """ Creates a feature object from the storage files data
        :param interface: (dict) the interface
        :param storage_features: (dict) the dictionary from the storage
        :returns: (Features)
        """
        new_features = Features(interface)

        # Parse
        new_features.data = cls.parse_features(new_features, storage_features, shorten_keys=False)
        new_features.len = len(new_features.data)

        return new_features


class Storage:
    """ Interface to the storage.json file
    """
    STORAGE_PATH = find_file("res\\storage.json")
    DEFAULT_TEMPLATE = {
        "api": "https://temp-fov-changer-site.herokuapp.com/api/",
        "mc_version": "",
        "features_help_url": "https://temp-fov-changer-site.herokuapp.com/docs/features/#{}",
        "features": {
            #  See storage.Features
        },
        "settings_help_url": "https://temp-fov-changer-site.herokuapp.com/docs/settings/",
        "settings": {
            "start_minimized": False,
            "auto_attach": False,
            "attach_cooldown": 5000
        }
    }

    def __init__(self, interface):
        """ Initialize
        :param interface: the interface
        """
        self.interface = interface

        # Stored
        self.data = None
        self.features = None
        self.settings_tk_vars = None

        # If the storage was changed frequently by a  process
        self.edited = False
        self.edited_lock = threading.Lock()

        # If the listener keys need to be updated
        self.listener_keys_edited = False
        self.listener_keys_edited_lock = threading.Lock()

        # If data can be already saved
        self.ready = False

        # Load data
        try:
            with open(self.STORAGE_PATH, "a+") as f:
                # Using a+ instead of w+ because it doesn't truncate
                f.seek(0)

                # If is written read, else write default
                if f.read() != "":
                    f.seek(0)
                    self.data = json.load(f)

                    # Validate
                    if not self.validate(self.data, self.DEFAULT_TEMPLATE):
                        raise FileNotFoundError

                else:
                    f.seek(0)
                    json.dump(self.DEFAULT_TEMPLATE, f, indent=4)
                    self.data = self.DEFAULT_TEMPLATE

        except (json.JSONDecodeError, FileNotFoundError):
            ui.queue_quit_message(self.interface, "Invalid storage file! Please correct or delete it!", "Fatal Error")

            # Add to the interface
            self.interface.update({"Storage": self})

            return

        # Add to the interface
        self.interface.update({"Storage": self})

        # If needed, parse old features
        if self.data and self.data["features"]:
            try:
                self.features = Features.from_storage_file(self.interface, self.data["features"])
                Logger.log("Loading stored features!")

            except MessageHandlingError as e:
                ui.queue_quit_message(self.interface, f"Invalid storage file! {e.message}", "Fatal Error")
                return

            self.ready = True

        # Settings: Start minimized
        if self.data["settings"]["start_minimized"]:
            self.interface["RootThread"].queue.append({"cmd": "hide", "params": [], "kwargs": {}, "wait_for_render": True})

        # Settings: Auto start
        if self.data["settings"]["auto_attach"]:
            self.interface["RootThread"].queue.append(
                {"cmd": lambda: self.interface["ProcessingThread"].queue.append(
                    {"cmd": "start_button_handle", "params": [None], "kwargs": {}}
                ), "params": [], "kwargs": {}, "wait_for_render": True, "attr": False})

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
            with open(self.STORAGE_PATH, "w+") as f:
                f.seek(0)
                json.dump(self.data, f, indent=4)
