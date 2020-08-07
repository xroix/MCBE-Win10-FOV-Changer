""" Handles verifying and fetching things out from an external service """

import binascii
import json

import requests

from src import ui
from src.logger import Logger
from src.processing import storage
from src.exceptions import MessageHandlingError


class Network:
    """ Handles authentication, fetching and api based stuff
    """

    def __init__(self, references: dict):
        """ Initialize
        :param references: the references
        """
        self.references = references

        self.storage = references["Storage"]

        # Add to references
        self.references.update({"Network": self})

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
                resp = requests.get(f"{self.storage.get('api')}offsets/{version_id}")
                Logger.log(f"Feature request number {tries}")

                # Too many request
                if resp.status_code == 429:
                    raise MessageHandlingError("Exceeded rate limit!")

                # Server fail
                elif resp.status_code != 200:
                    raise MessageHandlingError("Couldn't communicate with the server!")

                data = resp.json()
                status_code = data["status"]

                # Not found, there are no offsets for that version
                if status_code == 404:
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
                ui.queue_alert_message(self.references, e.message, warning=True)
                return False

            tries += 1

        if not data:
            Logger.log("Couldn't communicate with the server!")
            ui.queue_alert_message(self.references, "Couldn't communicate with the server!", warning=True)
            return False

        else:
            # Parse
            try:
                offs = json.loads(data["offsets"])

                # Parse server response
                self.storage.features = storage.Features.from_server_response(self.references, offs, saved_features=self.storage.features if self.storage.features else None)

            except (json.JSONDecodeError, binascii.Error):
                Logger.log("Invalid response from server!")
                ui.queue_alert_message(self.references, "Invalid response from server!", warning=True)
                return False

            except MessageHandlingError as e:
                Logger.log(e.message)
                ui.queue_alert_message(self.references, "Invalid offsets!", warning=True)
                return False

            self.storage.set("features", self.storage.features.for_json)
            self.storage.set("mc_version", current_version)

            self.storage.update_file()

            Logger.log("Saved new features and version")
            return True
