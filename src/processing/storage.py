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
        name = name.split("\\")[-1]

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
        self.child_format = self.storage.get("features")
        self.list_format = {}

        self.len = 0
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

    def __getitem__(self, item):
        """ Get a feature by id
        :param item: the feature id
        """
        if item in self.list_format:
            return self.list_format[item]

        else:
            return None

    @classmethod
    def from_server_response(cls, interface: dict, response_features: dict):
        """ Creates a feature object from the response features
        :param interface: the interface
        :param response_features: the dictionary from the server
        :returns: (Features)
        """

        new_feature = Features(interface)

        def inner(feature: Features, d: dict) -> dict:
            """ Recursive inner method
            :param feature: the new feature instance
            :param d: one layer of features, will get modified
            :returns: the new layer
            """
            # No .items() for reference
            for feature_id in d.copy():
                feature_value = d[feature_id]

                print("Parsing", feature_id)

                # Parse shorten keys
                for old_key, new_key in feature.hash_table.copy():
                    if old_key in feature_value:

                        # Change key
                        feature_value[new_key] = feature_value.pop(old_key)

                    else:
                        raise KeyError(f"missing {old_key}!")

                # Parse also children
                if feature_value["children"]:
                    inner(feature, feature_value["children"])  # Works because it has a working reference

            return d

        print(inner(new_feature, response_features))

        # # Iter through features, no items() to get a reference
        # for feature_id, feature_value in old.items():
        #     try:
        #         new.update({feature_id: {}})
        #
        #         # Keeps track to make sure each mask item is available
        #         needed = self.features_hash_table.copy()
        #
        #         # Through its shorten keys, eg 'a'
        #         for shorten_key, new_name in feature_value.items():
        #             new_value = {}
        #
        #             if shorten_key != "c":
        #                 new_value = new_value
        #
        #             # Children
        #             elif new_name:
        #                 # Parse them
        #                 parsed = self.parse_server_response(new_name)
        #                 i += parsed[1]
        #
        #                 new_value = parsed[0]
        #
        #             new[feature_id].update({self.features_hash_table[shorten_key]: new_value})
        #
        #             del needed[shorten_key]
        #
        #         if needed:
        #             raise Exception(f"Missing {needed}")
        #
        #         i += 1
        #
        #         # Add the reference
        #         self.storage.features_ref.update({feature_id: feature_value})
        #
        #     # Couldn't load it
        #     except Exception as e:
        #         if feature_id in new:
        #             del new[feature_id]
        #
        #         logger.logDebug(f"Could not load feature '{feature_value['n']}' -> {e.__class__.__name__} {e}")
        #
        #     logger.logDebug(f"Fetched feature '{feature_value['n']}'", add=True)
        #
        # return new, i

    def generate_list_format(self):
        """ Generates a list format
        """

        def inner(d: dict):
            for feature_id, feature_value in self.child_format.items():
                # do stuff

                if feature_value["children"]:
                    inner(feature_value["children"])

    @property
    def for_json(self) -> dict:
        """ Gives features ready for json parser
        """
        return self.child_format


class Storage:
    """ Interface to the storage.json file
    """
    STORAGE_PATH = find_file("res\\storage.json")
    DEFAULT_TEMPLATE = {
        "api": "http://127.0.0.1:5000/api/",
        "mc_version": "",
        "features": {
            # 0: {
            #     "name": "FOV",
            #     "available": True,
            #     "enabled": True,
            #     "key": "v",
            #     "offsets": [12, 12],
            #     "help": "https",
            #     "children": {}
            # },
        },
        "features_len": 0,
        "settings": {
            "start_cooldown": 5000
        }
    }

    def __init__(self, interface):
        """ Initialize
        :param interface: the interface
        """
        self.interface = interface

        self._data_ = None
        self.features = None

        try:
            with open(self.STORAGE_PATH, "a+") as f:
                # Using a+ instead of w+ because it doesn't truncate
                f.seek(0)

                # If is written read, else write
                if f.read() != "":
                    f.seek(0)
                    self._data_ = json.load(f)

                    # Validate
                    if not self.validate(self._data_, self.DEFAULT_TEMPLATE):
                        raise json.JSONDecodeError

                else:
                    f.seek(0)
                    json.dump(self.DEFAULT_TEMPLATE, f, indent=4)  # TODO invalid json handler
                    self._data_ = self.DEFAULT_TEMPLATE

        except json.JSONDecodeError:
            ui.queueQuitMessage(self.interface, "Invalid storage file! Please delete it!", "Fatal Error")

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
        self._data_[name] = value

    def get(self, name: str):
        """ Getter
        :param name: the name
        """
        return self._data_[name]

    def updateFile(self):
        """ Update file content
        """
        with open(self.STORAGE_PATH, "w+") as f:
            f.seek(0)
            json.dump(self._data_, f, indent=4)
