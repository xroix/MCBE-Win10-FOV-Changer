import time

import pypresence


class Discord:
    """ Handles the discord rich presence
    """

    def __init__(self, references: dict):
        """ Initialize
        :param references: (dict) the references
        """
        self.references = references

        self.client_id = "733376215737434204"
        self.rpc = pypresence.Presence(client_id=self.client_id)
        self.rpc.connect()

        self.last_server = None
        self.last_time = None

        # Add to references
        self.references.update({"Discord": self})

    def update(self, connected: bool, server: str, version: str):
        """ Updates the rich presence
        :param connected: if fov changer started and connected
        :param server: server domain
        :param version: mc version
        """
        # If in game
        if connected:
            # New server?
            print(server, self.last_server)
            print(self.last_time)
            if (not self.last_server and not self.last_time) or server != self.last_server:
                self.last_server = server
                self.last_time = int(time.time())

            # On server or in menus?
            details = f"Playing {server}" if server else "Main Menu"

            state = {"state": f"on {version}"} if version else {}

            self.rpc.update(details=details, large_image="logo-full", large_text="Using FOV Changer",
                            small_image="mc", small_text="Minecraft Bedrock",
                            start=self.last_time, **state)

        else:
            self.rpc.update(state="Ready to start", large_image="logo-full", large_text="Using FOV Changer")
