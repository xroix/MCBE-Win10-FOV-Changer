"""
Copyright 2020 XroixHD

REQUIREMENTS: pymem, pynput, colorama, requests
"""
import sys
import threading

import colorama

colorama.init()

# Rich text
reset = "\u001b[0m"
black = "\u001b[30m"
white = "\u001b[37m"
bright_blue = "\u001b[34;1m"
bright_red = "\u001b[31;1m"
bright_green = "\u001b[32;1m"
bright_black = "\u001b[90;1m"
bg_white = "\u001b[47m"
bg_bright_blue = "\u001b[44;1m"
bold = "\u001b[1m"

# Needed so that main thread gets killed
RUN = False
RUN_lock = threading.Lock()


def errorMSG(msg):
    global RUN

    print()
    print(bright_red + bold + "┌────────────────────────────────────────────────────────┐")
    print(f"┤ {msg}")
    print("└────────────────────────────────────────────────────────┘" + reset)
    input("Press any key to exit")

    # Kill while loop
    if RUN:
        with RUN_lock:
            RUN = False

    sys.exit()
