import pymem
from pynput import keyboard

from src.util import *


class Listener(keyboard.Listener):
    """ Listener for key events
    """

    def __init__(self, interface):
        """ Handles keyboard input
        :param interface: the interface
        """
        super().__init__(
            on_press=self.on_press,
            on_release=self.on_release
        )
        self.interface = interface

        self.gateway = interface["Gateway"]
        self.storage = interface["Storage"]

        self.pressed = False

    @staticmethod
    def unctrl(c: int) -> str:
        """ Convert hex c to ascii characters / control characters
        :param int c: the character value
        """
        # Control character
        if c <= 0x1f:
            return chr(c + 0x40)

        else:
            return chr(c)

    def on_press(self, key: keyboard.KeyCode):
        """ On press event
        :param key: the key code
        """
        try:
            if isinstance(key, keyboard.KeyCode):
                # Normalize
                code = self.unctrl(key.vk).lower()

                if self.pressed:
                    pass

                elif code == self.zoom_key:
                    self.pm.write_float(self.pm.fov_address, self.pm.zoom_fov)
                    self.pressed = True

        except pymem.exception.MemoryWriteError:
            errorMSG("Minecraft Bedrock was closed! or Something else went wrong!")

    def on_release(self, key: keyboard.KeyCode):
        """ On release event
        :param key: the key code
        """
        try:
            if isinstance(key, keyboard.KeyCode):
                # Normalize
                code = self.unctrl(key.vk).lower()

                print(ord(code), ord(self.zoom_key))

                if code == self.zoom_key:
                    self.pm.write_float(self.pm.fov_address, self.pm.normal_fov)
                    self.pressed = False

        except pymem.exception.MemoryWriteError:
            errorMSG("Minecraft Bedrock was closed! or Something else went wrong!")
