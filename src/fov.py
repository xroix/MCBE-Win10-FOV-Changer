"""
Copyright 2020 XroixHD

REQUIREMENTS: pymem, pynput, colorama, requests

CREDITS: Thanks to pymem's discord, they helped a lot
"""

from src import util
from src.data import storage
from src.util import *

# variables if no arguments are given
conf = storage.Config()
DEFAULT_ZOOM_FOV = conf.get("default_zoom_fov")
DEFAULT_NORMAL_FOV = conf.get("default_normal_fov")
DEFAULT_KEY = conf.get("default_zoom_key")


def run():
    """ The main run method
    """
    print(bright_blue + " ___  __           __                  __   ___  __  ")
    print("|__  /  \ \  /    /  ` |__|  /\  |\ | / _` |__  |__) ")
    print("|    \__/  \/     \__, |  | /~~\ | \| \__> |___ |  \ ")
    print("                                                     " + reset)
    print("┬─────────────────────────────────────────────────────────")
    print(f"└ Made by {bright_blue}XroixHD{reset} :]")
    print("\n")
    print(bright_black + "┌────────────────────────────────────────────────────────┐")
    print(f"┤ {bold}LOG (ignore):{reset}")
    print(bright_black + "├────────────────────────────────────────────────────────┤")

    # Storage
    st = storage.Storage()

    # Handle arguments
    args = sys.argv[1:]
    if len(args) == 3:
        pm = Pm(float(args[1]), float(args[2]), st, conf)
        listener = Listener(args[0], pm)

    else:
        pm = Pm(DEFAULT_ZOOM_FOV, DEFAULT_NORMAL_FOV, st, conf)
        listener = Listener(DEFAULT_KEY, pm)

    # Check mc version & get address
    pm.checkVersion()
    pm.getAddress()

    # Prettify
    print("└────────────────────────────────────────────────────────┘" + reset)
    print("\n")

    # Log settings
    print("┌────────────────────────────────────────────────────────┐")
    print(f"┤ {bold}SETTINGS:{reset}")
    print("├────────────────────────────────────────────────────────┤")
    print(f"│ {pm.zoom_fov=}")
    print(f"│ {pm.normal_fov=}")
    print(f"│ {listener.zoom_key=}")
    print("└────────────────────────────────────────────────────────┘")
    print("\n")

    # Start Listener
    listener.start()

    # Set up conditional
    with util.RUN_lock:
        util.RUN = True

    while True:
        # Needed so that it is mortal
        with util.RUN_lock:
            if not util.RUN:
                break

        print(f"├ Stop FOV Changer? {bright_green}Y{reset} / {bright_red}n{reset} ", end="")
        if input() == "Y":
            break
