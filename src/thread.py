""" Threads, own file because of circular imports ._."""

import threading
import time
import types

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

        self.running = False

        self.i = 0
        self.i_end = 0

        self.wait_time = wait_time

        # Load all scheduled tasks / methods / functions
        for name in self.scheduled_methods:
            f = getattr(self, name).__func__
            seconds = f.seconds

            # Add to .tasks
            if seconds in self.tasks:
                self.tasks[seconds].add(f)

            else:
                self.tasks.update({seconds: {f}})

            # Highest interval?
            if seconds > self.i_end * self.wait_time:
                self.i_end = seconds / self.wait_time

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
            self.running = True
            while self.running:

                # Execute scheduled methods
                seconds = self.i * self.wait_time

                if seconds in self.tasks:
                    for method in self.tasks[seconds]:
                        method(self)

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
                if self.i >= self.i_end:
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

            def __set_name__(self, owner, name):
                """ Will get executed when the function gets assigned to class
                :param self: the owner obj
                :param owner: the owner obj
                :param name: the name of the new function
                """
                # Note function5
                if not hasattr(owner, "scheduled_methods"):
                    owner.scheduled_methods = {name}

                else:
                    owner.scheduled_methods.add(name)

                # Restore old function
                setattr(owner, name, self.f)

            f = staticmethod(f)

            # Save it
            f.__func__.seconds = seconds

            # Create the temporary object
            temp_f = type(f"temp_{f.__func__.__name__}", (object,), {
                "__set_name__": __set_name__,
                "f": f
            })()

            return temp_f

        return inner
