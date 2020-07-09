import json
import os
import sys

from src import logger
from src import ui


def find_file(name):
    """ Find filename, see: https://cx-freeze.readthedocs.io/en/latest/faq.html#using-data-files
    """
    if hasattr(sys, "frozen"):
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
        self.keys = {}
        self.len = 0

        # Parsing the shorten keys from server response
        # and check if something is missing
        self.hash_table = {
            "n": "name",  # The name
            "a": "available",  # If it is available
            "e": "enabled",  # Enabled?
            "k": "key",  # Key bind
            "h": "help",  # Help url
            "v": "value",  # [type, before, after]
            "o": "offsets",  # Offsets
            "c": "children"  # Children features
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

    @classmethod
    def parse_shorten_keys(cls, features, response_features: dict):
        """ Parses shorten keys, creates feature.keys (dict)
        :param features: (Features) the new features instance
        :param response_features: the response features unparsed
        """
        # No .items() for reference
        for feature_id in response_features.copy():
            feature_value = response_features[feature_id]

            # Parse shorten keys, note: items makes a copy
            for old_key, new_key in features.hash_table.items():
                if old_key in feature_value:

                    # Change key
                    feature_value[new_key] = feature_value.pop(old_key)

                else:
                    raise KeyError(f"Key '{old_key}' is missing in response!")
                
            # Add the key to the keys
            features.keys.update({feature_id: feature_value["key"]})

        return response_features

    @classmethod
    def from_server_response(cls, interface: dict, response_features: dict):
        """ Creates a feature object from the response features
        :param interface: (dict) the interface
        :param response_features: (dict) the dictionary from the server
        :returns: (Features)
        """
        new_features = Features(interface)

        # Parse
        new_features.data = cls.parse_shorten_keys(new_features, response_features)
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
        new_features.data = storage_features
        new_features.len = len(new_features.data)

        return new_features


class Storage:
    """ Interface to the storage.json file
    """
    STORAGE_PATH = find_file("res\\storage.json")
    DEFAULT_TEMPLATE = {
        "api": "http://127.0.0.1:5000/api/",
        "mc_version": "",
        "features": {
            # 0: { TODO update comment template
            #     "name": "FOV",
            #     "available": True,
            #     "enabled": True,
            #     "key": "v",
            #     "offsets": [12, 12],
            #     "help": "https",
            #     "children": []
            # },
        },
        "settings": {
            "start_cooldown": 5000
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
                        raise json.JSONDecodeError

                else:
                    f.seek(0)
                    json.dump(self.DEFAULT_TEMPLATE, f, indent=4)
                    self.data = self.DEFAULT_TEMPLATE

        except (json.JSONDecodeError, FileNotFoundError):
            ui.queueQuitMessage(self.interface, "Invalid storage file! Please correct or delete it!", "Fatal Error")

        # If needed, parse old features
        if self.data["features"]:
            self.features = Features.from_storage_file(self.interface, self.data["features"])
            logger.logDebug("Loading stored features!")

        # Finish and add to the interface
        self.interface.update({"Storage": self})
        logger.logDebug("Storage", add=True)

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

    def updateFile(self):
        """ Update file content
        """
        with open(self.STORAGE_PATH, "w+") as f:
            f.seek(0)
            json.dump(self.data, f, indent=4)
