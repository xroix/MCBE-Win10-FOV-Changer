import sys
import time
import logging
import traceback
import tkinter as tk
from tkinter import messagebox


logger = logging.getLogger(__name__)


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
    # So that our gui logging handler does not crash
    if "RootThread" in references:
        references["RootThread"].is_mainloop_running = False

    # Add traceback to log
    logger.exception(
        "FOV-Changer has crashed!",
        exc_info=True,
        stack_info=True
    )

    # Notify user
    messagebox.showerror(title="Critical Error", message="FOV-Changer crashed! Check log.txt for more insight.\n\nIf you need help, feel free to join our Discord or open up an issue on GitHub. Please make sure to include the log.txt file created next to FOV-Changer.")

    # Kill all
    references["SystemTray"].stop_tray()
