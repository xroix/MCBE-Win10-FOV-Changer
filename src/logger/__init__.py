import threading
import time
import tkinter as tk

DEBUG = True


class Logger:
    """ A class with class attributes and methods for logging,
        It uses no instances because to be available everywhere + laziness
    """

    references = None
    root = None

    queue = []
    queue_lock = threading.Lock()

    @classmethod
    def init(cls, references):
        """ "Initialize" class
        :param references: the references
        """
        cls.references = references

    @classmethod
    def log(cls, msg: str, *, add=None):
        """ Debug logs a message,
        :param msg: the message
        :param add: if it is + or -
        """
        # Get time for new txt
        new_msg = f"{time.strftime('[%H:%M:%S] ', time.localtime(time.time()))}"

        if add:
            new_msg += f"+ {msg}"

        # Cant use not because none is also "false"
        elif add is False:
            new_msg += f"- {msg}"

        else:
            new_msg += f"> {msg}"

        print(new_msg)
        with cls.queue_lock:
            cls.queue.append(new_msg)

    @classmethod
    def write_all(cls):
        """ Dumps all text in queue onto the log
        """
        # Load queue if not done
        if not cls.root:
            cls.root = cls.references["Root"]

        if cls.root.log_text:
            # Load messages and clear queue
            with cls.queue_lock:
                msg = "\n".join(cls.queue) + "\n"
                cls.queue = []

            cls.root.log_text.config(state="normal")
            cls.root.log_text.insert("end", msg)
            cls.root.log_text.config(state="disabled")
