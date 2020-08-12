import time

import pypresence


class Discord:
    """ Handles the discord rich presence
    """

    def __init__(self, references: dict, loop):
        """ Initialize
        :param references: (dict) the references
        """
        self.references = references

        self.rpc = pypresence.Presence(client_id="733376215737434204", loop=loop)
        self.rpc.connect()

        self.last_server = None
        self.last_time = None

        self.partner_servers = {
            "hivebedrock.network": "The Hive",
            "inpvp.net": "Mineville",
            "mineplex.com": "Mineplex",
            "galaxite.net": "Galaxite",
            "lbsg.net": "Lifeboat",
            "cubecraft.net": "CubeCraft"
        }

        self.feature = None

        # For ui
        self.tk_vars = {}

        # Add to references
        self.references.update({"Discord": self})

    @staticmethod
    def get_server_part(server) -> str:
        """ Get the needed part from server ip / domain for the partner_servers hash table
        :param server: server domain
        :returns: needed part from server domain
        """
        return ".".join(server.split(".")[-1:-3:-1][::-1])

    def update(self, connected: bool, server: str, version: str):
        """ Updates the rich presence
        :param connected: if fov changer started and connected
        :param server: server domain
        :param version: mc version
        """
        if not self.feature:
            self.feature = self.references["Storage"].features["3"]

        # If in game
        if connected:
            # New server?
            if (not self.last_server and not self.last_time) or server != self.last_server:
                self.last_server = server
                self.last_time = int(time.time())

            # Do not show server
            if not self.feature["settings"]["show_server"]:
                details = "Playing"

            # Connected to server
            elif server:
                # Check if server is partnered
                if (part := self.get_server_part(server)) in self.partner_servers:
                    server = self.partner_servers[part]

                details = f"Playing {server}"

            # Main menu or private world todo
            else:
                details = "Main Menu"

            state = {"state": f"on {version}"} if version and self.feature["settings"]["show_version"] else {}

            self.rpc.update(details=details, large_image="logo-full", large_text="Using FOV Changer",
                            small_image="mc", small_text="Minecraft Bedrock",
                            start=self.last_time, **state)

        else:
            self.rpc.update(state="Ready to start", large_image="logo-full", large_text="Using FOV Changer")
