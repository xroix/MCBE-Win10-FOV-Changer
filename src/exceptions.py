import sys
import time
import traceback
import tkinter as tk
from tkinter import messagebox

from src.logger import Logger


# Override tkinter exception handler
tk.Tk.report_callback_exception = lambda self, exc, val, tb: handle(self.interface)


class MessageHandlingError(Exception):
    """ A exception to passes on a message to except clause
    """

    def __init__(self, message):
        """ Initialize
        :param message: the error message
        """
        self.message = message


def handle(interface: dict):
    """ Handle a exception
    :param interface: (dict) the interface
    """
    tb = traceback.format_exc()
    msg = f"----------------------------------------{time.strftime('[%d.%m.%Y - %H:%M:%S]', time.localtime(time.time()))}----------------------------------------\n"

    # If available, write log from log_text
    if "Root" in interface and interface["Root"].log_text:
        interface["Root"].log_text.config(state="normal")
        msg += interface["Root"].log_text.get("1.0", "end")

    # or from the logger queue
    if Logger.queue:
        msg += "\n".join(Logger.queue) + "\n"

    # Add the traceback
    msg += f"{tb}\n\n"

    # Write crash log
    with open("crash_log.txt", "w+") as f:
        f.write(msg)

    # If available, notify
    if "RootThread" in interface:
        messagebox.showerror(title="Fatal Error", message="Something bad happened! Check crash_log.txt for more insight!")

    # Kill all
    interface["SystemTray"].stop_tray()
    sys.exit(0)
