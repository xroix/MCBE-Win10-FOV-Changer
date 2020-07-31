import sys
import time
import traceback
import tkinter as tk
from tkinter import messagebox

from run import DEBUG
from src.logger import Logger


# Override tkinter exception handler
tk.Tk.report_callback_exception = lambda self, exc, val, tb: handle_error(self.references)


class MessageHandlingError(Exception):
    """ A exception to passes on a message to except clause
    """

    def __init__(self, message):
        """ Initialize
        :param message: the error message
        """
        self.message = message


def handle_error(references: dict):
    """ Handle a exception
    :param references: (dict) the references
    :raises: the last error if project is in debug mode
    """
    if DEBUG:
        raise

    # Extract traceback and start formatting message
    tb = traceback.format_exc()
    msg = f"----------------------------------------{time.strftime('[%d.%m.%Y - %H:%M:%S]', time.localtime(time.time()))}----------------------------------------\n"

    # If available, write log from log_text
    if "Root" in references and references["Root"].log_text:
        references["Root"].log_text.config(state="normal")
        msg += references["Root"].log_text.get("1.0", "end")

    # or from the logger queue
    if Logger.queue:
        msg += "\n".join(Logger.queue) + "\n"

    # Add the traceback
    msg += f"{tb}\n\n"

    # Write crash log
    with open("crash_log.txt", "w+") as f:
        f.write(msg)

    # If available, notify
    if "RootThread" in references:
        messagebox.showerror(title="Fatal Error", message="Something bad happened! Check crash_log.txt for more insight!")

    # Kill all
    references["SystemTray"].stop_tray()
    sys.exit(0)
