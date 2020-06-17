import base64
import json
import zlib

import requests
import licensing.models as models
import licensing.methods as methods

from src import logger, ui
from src.processing import storage


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


class ErrorHandlingException(Exception):
    """ A exception to pass its message on in network passed situations
    """

    def __init__(self, message):
        """ Initialize
        :param message: the error message
        """
        self.message = message


class Network:
    """ Handles authentication, fetching and api based stuff
    """

    def __init__(self, interface: dict):
        """ Initialize
        :param interface: the interface
        """
        self.interface = interface

        self.storage = interface["Storage"]

        self.product_id = 6345
        self.pub_key = "<RSAKeyValue><Modulus>41jDl8UXM1e8OZKduBL7EGaP3ibCOPMGOKOG57vIfK0pSPgsY014IbO7RZCtiEpUjra2TTaQO7" \
                       "+mCrIkx2P2RNTZ2z5rDbkb7/Plaso/fJN/L8qu71Ohc3sXZKo299Qz6Z2wZ7FiaXVqi5gtg9HsLqjTzihpWs7LNjo" \
                       "+El125LBVp63H3Q83ivq43jYObPk8hY+zcRJOIKLlQY1akAtKWegTzmvtOc3Ydwgg4m9pof/21pfy" \
                       "/7JzaSY2NP4bLbSLu404QTMdtR6tspYgHpDZyzgXtNXezDiEASfqbkkrGn8e2ZRpjsNsHJlyH7UXH7mV06S00gcW/ne+3gH1dFXH2Q" \
                       "==</Modulus><Exponent>AQAB</Exponent></RSAKeyValue>"
        self.activate_token = "WyIyMjg5NCIsIjFaNzBHeGRFUVpqenhVNlJKMGQzMzhjQ0hsNHVmOHpHRXhtSTl1MXoiXQ=="
        self.data_obj_token = "WyIyMjk1NSIsIkVwakpIU2FjRVgxeEpQOWxheE1HcjBvbzZaeHFOU3NGcFZmdTZQOHYiXQ=="
        self.api_key = ""

        self.license_key = ""
        self.license_obj = None

    def authenticate(self, license_key: str) -> tuple:
        """ Authenticate the given license key
        :param license_key: license key
        """
        self.license_key = license_key

        resp = methods.Key.activate(token=self.activate_token, rsa_pub_key=self.pub_key, product_id=self.product_id,
                                    key=self.license_key, machine_code=methods.Helpers.GetMachineCode(),
                                    floating_time_interval=300, max_overdraft=0)

        # Check if key is valid
        if not self.checkKeyObject(resp[0]):
            logger.logDebug("Invalid license!")

            return False, resp[1] if isinstance(resp[1], str) else "Wrong machine!"

        else:
            logger.logDebug("Authenticated license!")

            # Save license object
            self.license_obj = resp[0]
            self.saveKey(self.license_obj)

            return True, ""

    @staticmethod
    def checkKeyObject(license_obj: models.LicenseKey) -> bool:
        """ Checks if a key is valid, own method, because it is used at several locations
        :param license_obj: (LicenseKey) a license key object
        """
        if not license_obj or not methods.Helpers.IsOnRightMachine(license_obj, is_floating_license=True,
                                                                   allow_overdraft=False):
            return False

        return True

    def isValidKey(self) -> bool:
        """ Tests if a valid key is saved, if saved, self.license_obj gets updated
        :returns: (tuple) success boolean
        """
        license_obj = self.getKey()

        if self.checkKeyObject(license_obj):
            self.license_obj = license_obj
            self.license_key = self.license_obj.key

            return True

        return False

    @staticmethod
    def saveKey(license_obj: models.LicenseKey):
        """ Saves the license to a file
        :param license_obj: (LicenseKey) license key object
        """
        with open(storage.find_file("LICENSE_KEY"), "w+") as f:
            f.write(license_obj.save_as_string())

    def getKey(self) -> models.LicenseKey:
        """ Gets license from file, valid for 30 days
        :returns: (LicenseKey) a license key object
        """
        with open(storage.find_file("LICENSE_KEY"), "a+") as f:
            f.seek(0)
            license_obj = models.LicenseKey.load_from_string(self.pub_key, f.read(), 30)

        return license_obj

    def generateNewApiKey(self):
        """ Generates a new api key, server stores it in a data object
        :raises: a exception for invalid status codes
        """
        resp = requests.get(f"{self.storage.get('api')}api_key/generate", params={"license": self.license_key})

        # Server fail
        if resp.status_code != 200:
            raise ErrorHandlingException("Couldn't fetch a new api key!")

        status_code = resp.json()["status"]

        # Api key not expired, but got to this method, so try again later
        if status_code == 409:
            logger.logDebug(resp.json()["message"])
            raise ErrorHandlingException("Please try it later again!")

        # Success
        elif status_code == 200:
            logger.logDebug("New api key generated!")

        else:
            logger.logDebug(resp.json()["message"])
            raise ErrorHandlingException("Couldn't fetch a new api key!")

    def fetchApiKey(self) -> any:
        """ Retrieves api key from the data object
        :returns: the response
        """
        data = list_data_objects_to_key(self.data_obj_token, self.product_id, self.license_key)
        self.api_key = [x for x in data["dataObjects"] if x["name"] == "api_key"][0]["stringValue"]

    def fetchFeatures(self, current_version: str) -> bool:
        """ Fetch the data from the api
        :param current_version: current mc version
        :returns: if succeed
        """
        version_id = "".join(current_version.split("."))
        logger.logDebug(f"Getting features for '{version_id}'")

        # Api key wasn't fetched before
        if not self.api_key:
            self.fetchApiKey()
            logger.logDebug(f"Fetched api key")

        # Retry certain times
        data = None
        tries = 0
        while tries <= 2:
            try:
                resp = requests.get(f"{self.storage.get('api')}offsets/{version_id}", params={"api_key": self.api_key})
                logger.logDebug(f"Feature request number {tries}")

                # Too many request
                if resp.status_code == 429:
                    raise ErrorHandlingException("Exceeded rate limit!")

                # Server fail
                elif resp.status_code != 200:
                    raise ErrorHandlingException("Couldn't communicate with the server!")

                data = resp.json()
                status_code = data["status"]

                # Forbidden, new api key needed
                if status_code == 440:
                    logger.logDebug(f"New api key needed!")
                    self.generateNewApiKey()
                    self.fetchApiKey()

                # Not found, there are no offsets for that version
                elif status_code == 404:
                    raise ErrorHandlingException("Minecraft version is unsupported!")

                # Success
                elif status_code == 200:
                    break

                # Else, something went wrong
                else:
                    raise ErrorHandlingException("Couldn't fetch new offsets!")

            except requests.exceptions.ConnectionError:
                pass

            # Alert message
            except ErrorHandlingException as e:
                logger.logDebug(e.message)
                ui.queueAlertMessage(self.interface, e.message, warning=True)
                break

            tries += 1
        
        if not data:
            logger.logDebug("Couldn't communicate with the server!")
            ui.queueAlertMessage(self.interface, "Couldn't communicate with the server!", warning=True)
            return False
            
        else:
            # Decompress
            try:
                offs = json.loads(zlib.decompress(base64.b64decode(data["offsets"].encode("utf8"))).decode("utf8"))

            except json.JSONDecodeError:
                logger.logDebug("Invalid offsets!")
                ui.queueAlertMessage(self.interface, "Invalid offsets!", warning=True)
                return False

            # Update storage
            self.storage.features = storage.Features.from_server_response(self.interface, offs)

            self.storage.set("features", self.storage.features.for_json)
            self.storage.set("features_len", 3)  # TODO len
            self.storage.set("mc_version", current_version)
            self.storage.updateFile()

            logger.logDebug("Saved new features and version")
            return True
