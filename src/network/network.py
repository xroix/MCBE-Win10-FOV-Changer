""" Handles verifying and fetching things out from an external service """

import base64
import binascii
import json
import zlib

import requests
import licensing.models as models
import licensing.methods as methods

from src import ui
from src.logger import Logger
from src.processing import storage
from src.exceptions import MessageHandlingError


def list_data_objects_to_key(token, product_id, key, *, contains="", v=1):
    """ List data objects (variables) from a key
    :param token: the access token
    :param product_id: id of the product
    :param key: the license key
    :param contains: show only objs who contains given name
    :param v: method version
    """
    params = {
        "token": token,
        "ProductId": product_id,
        "Key": key,
        "Contains": contains,
        "v": v
    }
    return requests.get("https://app.cryptolens.io/api/data/ListDataObjectsToKey", params=params).json()


class Network:
    """ Handles authentication, fetching and api based stuff
    """

    def __init__(self, interface: dict):
        """ Initialize
        :param interface: the interface
        """
        self.interface = interface

        self.storage = interface["Storage"]

        # Cryptolens
        self.product_id = 6973
        self.pub_key = "<RSAKeyValue><Modulus>41jDl8UXM1e8OZKduBL7EGaP3ibCOPMGOKOG57vIfK0pSPgsY014IbO7RZCtiEpUjra2TTaQO7" \
                       "+mCrIkx2P2RNTZ2z5rDbkb7/Plaso/fJN/L8qu71Ohc3sXZKo299Qz6Z2wZ7FiaXVqi5gtg9HsLqjTzihpWs7LNjo" \
                       "+El125LBVp63H3Q83ivq43jYObPk8hY+zcRJOIKLlQY1akAtKWegTzmvtOc3Ydwgg4m9pof/21pfy" \
                       "/7JzaSY2NP4bLbSLu404QTMdtR6tspYgHpDZyzgXtNXezDiEASfqbkkrGn8e2ZRpjsNsHJlyH7UXH7mV06S00gcW/ne+3gH1dFXH2Q" \
                       "==</Modulus><Exponent>AQAB</Exponent></RSAKeyValue>"
        self.activate_token = "WyIzOTY0MCIsImwyVXc1U0IyLzNiV1dBMm5NS0x4NlVCbmZEcm5DU2pLMkRhbFVEMFciXQ=="
        self.data_obj_token = "WyIzOTY0MyIsIjNQbVRtM3U1bmZJcTlOMGMwZ0FaSEdJcEZGOThhZkZvT2ZJeU5Yb2wiXQ=="

        # Used to access certain endpoints
        self.api_key = ""

        # License
        self.license_key = ""
        self.license_obj = None

        # Add to interface
        self.interface.update({"Network": self})

    def authenticate(self, license_key: str) -> tuple:
        """ Authenticate the given license key
        :param license_key: license key
        """
        self.license_key = license_key

        resp = methods.Key.activate(token=self.activate_token, rsa_pub_key=self.pub_key, product_id=self.product_id,
                                    key=self.license_key, machine_code=methods.Helpers.GetMachineCode(),
                                    floating_time_interval=300, max_overdraft=0)

        # Check if key is valid
        if not self.check_key_object(resp[0]):
            Logger.log("Invalid license!")

            return False, resp[1] if isinstance(resp[1], str) else "Wrong machine!"

        else:
            Logger.log("Authenticated license!")

            # Save license object and license to file
            self.license_obj = resp[0]
            self.save_key(self.license_obj)

            return True, ""

    @staticmethod
    def check_key_object(license_obj: models.LicenseKey) -> bool:
        """ Checks if a key is valid, own method, because it is used at several locations
        :param license_obj: (LicenseKey) a license key object
        """
        if not license_obj or not methods.Helpers.IsOnRightMachine(license_obj, is_floating_license=True,
                                                                   allow_overdraft=False):
            return False

        return True

    def is_valid_key(self) -> bool:
        """ Tests if a valid key is saved, if saved, self.license_obj gets updated
        :returns: (tuple) success boolean
        """
        license_obj = self.get_key()

        if self.check_key_object(license_obj):
            self.license_obj = license_obj
            self.license_key = self.license_obj.key

            return True

        return False

    @staticmethod
    def save_key(license_obj: models.LicenseKey):
        """ Saves the license to a file
        :param license_obj: (LicenseKey) license key object
        """
        with open(storage.find_file("LICENSE_KEY"), "w+") as f:
            f.write(license_obj.save_as_string())

    def get_key(self) -> models.LicenseKey:
        """ Gets license from file, valid for 30 days
        :returns: (LicenseKey) a license key object
        """
        with open(storage.find_file("LICENSE_KEY"), "a+") as f:
            f.seek(0)
            license_obj = models.LicenseKey.load_from_string(self.pub_key, f.read(), 30)

        return license_obj

    def generate_new_api_key(self):
        """ Generates a new api key, server stores it in a data object
        :raises: a exception for invalid status codes
        """
        resp = requests.get(f"{self.storage.get('api')}api_key/generate", params={"license": self.license_key})

        # Server fail
        if resp.status_code != 200:
            raise MessageHandlingError("Couldn't fetch a new api key!")

        status_code = resp.json()["status"]

        # Api key not expired, but got to this method, so try again later
        if status_code == 409:
            Logger.log(resp.json()["message"])
            raise MessageHandlingError("Please try it later again!")

        # Success
        elif status_code == 200:
            Logger.log("New api key generated!")

        else:
            Logger.log(resp.json()["message"])
            raise MessageHandlingError("Couldn't fetch a new api key!")

    def fetch_api_key(self) -> bool:
        """ Retrieves api key from the data object
        """
        data = list_data_objects_to_key(self.data_obj_token, self.product_id, self.license_key)
        self.api_key = [x for x in data["dataObjects"] if x["name"] == "api_key"]

        if self.api_key:
            self.api_key = self.api_key[0]["stringValue"]
            return True

        else:
            self.generate_new_api_key()
            return False

    def fetch_features(self, current_version: str) -> bool:
        """ Fetch the data from the api
        :param current_version: current mc version
        :returns: if succeed
        """
        version_id = "".join(current_version.split("."))
        Logger.log(f"Getting features for '{version_id}'")

        # Retry certain times
        data = None
        tries = 0
        while tries <= 3:
            try:

                # Api key wasn't fetched before
                if not self.api_key:
                    if not self.fetch_api_key():
                        tries += 1
                        continue

                    Logger.log(f"Fetched api key")

                resp = requests.get(f"{self.storage.get('api')}offsets/{version_id}", params={"api_key": self.api_key})
                Logger.log(f"Feature request number {tries}")

                # Too many request
                if resp.status_code == 429:
                    raise MessageHandlingError("Exceeded rate limit!")

                # Server fail
                elif resp.status_code != 200:
                    raise MessageHandlingError("Couldn't communicate with the server!")

                data = resp.json()
                status_code = data["status"]

                # Forbidden, new api key needed
                if status_code == 440:
                    Logger.log(f"New api key needed!")
                    self.generate_new_api_key()
                    self.fetch_api_key()

                # Not found, there are no offsets for that version
                elif status_code == 404:
                    raise MessageHandlingError("Minecraft version is unsupported!")

                # Success
                elif status_code == 200:
                    break

                # Else, something went wrong
                else:
                    raise MessageHandlingError("Couldn't fetch new offsets!")

            except requests.exceptions.ConnectionError:
                pass

            # Alert message
            except MessageHandlingError as e:
                Logger.log(e.message)
                ui.queue_alert_message(self.interface, e.message, warning=True)
                return False

            tries += 1

        if not data:
            Logger.log("Couldn't communicate with the server!")
            ui.queue_alert_message(self.interface, "Couldn't communicate with the server!", warning=True)
            return False

        else:
            # Decompress and parse
            try:
                offs = json.loads(zlib.decompress(base64.b64decode(data["offsets"].encode("utf8"))).decode("utf8"))

                # Parse server response
                self.storage.features = storage.Features.from_server_response(self.interface, offs, saved_features=self.storage.features if self.storage.features else None)

            except (json.JSONDecodeError, binascii.Error):
                Logger.log("Invalid response from server!")
                ui.queue_alert_message(self.interface, "Invalid response from server!", warning=True)
                return False

            except MessageHandlingError as e:
                Logger.log(e.message)
                ui.queue_alert_message(self.interface, "Invalid offsets!", warning=True)
                return False

            self.storage.set("features", self.storage.features.for_json)
            self.storage.set("mc_version", current_version)
            self.storage.ready = True

            self.storage.update_file()

            Logger.log("Saved new features and version")
            return True
