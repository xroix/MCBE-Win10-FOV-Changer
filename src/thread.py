""" Threads, own file because of circular imports ._."""

import threading
import time

from src import exceptions


class Thread(threading.Thread):
    """ Extends the thread functionality
    """

    def __init__(self, references, name, wait_time):
        """ Initialize
        :param references: the references
        :param name: thread name
        :param wait_time: time between intervals
        """
        super().__init__(name=name)
        self.references = references

        self.queue = []
        self.tasks = {}

        self.running = True

        self.i = 0
        self.i_end = 0

        self.wait_time = wait_time

    def at_start(self):
        """ Gets called before the loop
        """
        raise NotImplementedError("Must override at_start() method!")

    def at_end(self):
        """ Gets called after loop
        """
        raise NotImplementedError("Must override at_end() method!")

    def run(self) -> None:
        """ Run method of thread, will loop as long .running is true
        """
        try:
            self.at_start()

            # Loop
            while self.running:

                # Execute scheduled methods
                seconds = self.i / self.wait_time

                if seconds in self.tasks:
                    for method in self.tasks[seconds]:
                        method()

                # Execute queued methods
                if self.queue:
                    task = self.queue.pop(0)

                    # Attribute of thread
                    if isinstance("cmd", str):
                        return_value = getattr(self, task["cmd"])(*task["params"], **task["kwargs"])

                    # Callable method
                    elif callable(task["cmd"]):
                        return_value = task["cmd"](*task["params"], **task["kwargs"])

                    else:
                        return_value = None

                    # Check if there is a callback
                    if "callback" in task:
                        task["callback"](return_value)

                # Highest value?
                if self.i > self.i_end:
                    self.i = 0

                else:
                    self.i += 1

                time.sleep(self.wait_time)

            self.at_end()

        # Handle all exceptions
        except Exception as e:
            exceptions.handle_error(self.references)

    @staticmethod
    def schedule(seconds=0):
        """ Decorator for scheduling a task
        :param seconds: the seconds to wait between
        """

        def inner(f):
            """"""
            self = f.__self__

            # Add to tasks
            if seconds in self.tasks:
                self.tasks[seconds].add(f)

            else:
                self.tasks.update({seconds: {f}})

            # Highest interval?
            if seconds > self.i_end:
                self.i_end = seconds

            return f

        return inner
