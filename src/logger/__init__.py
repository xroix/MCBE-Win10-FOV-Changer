"""
Logging using the built-in logging library of Python

Use following snippet to use the logger inside a source file:
```python 
import logging
logger = logging.getLogger(__name__)
```
"""

import queue
import time
import logging
import logging.config
import threading
import tkinter as tk


CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "[%(asctime)s] %(message)s",
            "datefmt": "%H:%M:%S"
        },
        "normal": {
            "format": "[%(asctime)s - %(threadName)s] \t%(levelname)s: %(message)s",
            "datefmt": "%H:%M:%S"
        },
        "detailed": {
            "format": "%(asctime)s - %(threadName)s - %(name)s - %(levelname)s: %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S%z"
        }
    },
    "handlers": {
        "gui": {
            "()": "ext://src.logger.GuiHandler",
            "level": "INFO",
            "formatter": "simple"
        },
        "stdout": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "normal",
            "stream": "ext://sys.stdout"
        },
        "file": {
            "class": "logging.FileHandler",
            "level": "DEBUG",
            "formatter": "detailed",
            "filename": "log.txt",
            "encoding": "utf-8",
            "mode": "w"   
        },
        # This queue handlers configuration is only possible since Python 3.12
        # Due to the added .listener property when using dictConfig
        # See: https://rob-blackbourn.medium.com/how-to-use-python-logging-queuehandler-with-dictconfig-in-python-3-12-3bbef42c5e20
        "queue_handler": {
            "class": "logging.handlers.QueueHandler",
            "handlers": [
                "gui",
                "stdout",
                "file"
            ]
        }
    },
    "loggers": {
        "root": {
            "level": "WARNING",
            "handlers": ["queue_handler"]
        },
        # Only our loggers shall pass every log record to the handlers
        # Third-party libraries get routed directly through the root logger, only passing WARNING log records
        "src": {
            "level": "DEBUG"
        }
    }
}


def start_logging():
    """ Required to be called at the start, so that logging works
    """
    logging.config.dictConfig(CONFIG)

    # Enable the QueueListener-Thread, which writes our messages non-blockingly
    logging.getHandlerByName("queue_handler").listener.start()

    # Set higher requirement for loggers from third-party libraries
    logging.getLogger("PIL").setLevel(logging.ERROR)

    # Test
    l = logging.getLogger(__name__)
    l.debug("Logging has started")


def stop_logging():
    """ Makes sure that every message left is written before we quit
    """
    logging.getHandlerByName("queue_handler").listener.stop()


class GuiHandler(logging.Handler):
    """ Custom handler to add log records to the "Log" tab inside the ui
    """

    def __init__(self, level = 0):
        """ Until this object receives its target tk.Text widget, it will buffer all messages
        """
        super().__init__(level)

        self.references: dict = None
        self.widget: logging.LogRecord | None = None
        self.queue = queue.Queue()

    def set_widget(self, references: dict, widget: tk.Text):
        """ Requires the target tk.Text widget to add the log records
        :param references:
        :param widget: said tk.Text
        """
        self.references = references
        self.widget = widget

        def in_root_thread():
            self.widget.config(state="normal")

            while self.queue.qsize() != 0:
                old_record = self.queue.get()

                self.widget.insert("end", f"{self.format(old_record)}\n")

            self.widget.config(state="disabled")

        # Log all log records that have been saved prior
        if self.references and self.references["RootThread"].is_mainloop_running:
            self.widget.after(0, in_root_thread)

    def emit(self, record: logging.LogRecord):
        """ Get called with passed on log record
        :param record: the log record
        """
        # The tk.Text widget is only created after some time,
        # until then we buffer all log records
        if not self.widget or not self.references:
            self.queue.put(record)
            return

        def in_root_thread():
            self.widget.config(state="normal")
            self.widget.insert("end", f"{self.format(record)}\n")
            self.widget.config(state="disabled")

        if self.references and self.references["RootThread"].is_mainloop_running:
            self.widget.after(0, in_root_thread)
