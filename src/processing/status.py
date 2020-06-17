class Status:
    """ Class for storing, accessing and editing statuses
    """

    def __init__(self, *args):
        """ Initialize
        :param args: the methods
        """
        self._status_ = dict.fromkeys(args, None)
        self._events_ = dict.fromkeys(args, set())

    def __iter__(self) -> iter:
        """ Iter through all statuses
        :returns: iterable, name -> status
        """
        yield from self._status_.items()

    def __setitem__(self, key: any, value: any):
        """ Subscribe to a event (when a status changes)
        :param key: the status name
        :param value: the function to invoke with the attr (new state)
        """
        self._events_[key].add(value)

    def set(self, name: str, key: bool):
        """ Set a status
        :param name: the name of the status
        :param key: new value
        """
        # Toggle Status
        _old = self._status_[name]
        self._status_[name] = key

        # Fire on events
        if _old is not key:
            state = self._status_[name]
            for i in self._events_[name]:
                i(state)

    def toggle(self, name: str):
        """ Toggle a status
        :param name: the name of the status
        """
        # Toggle status
        self._status_[name] = not self._status_[name]

        # Fire on events
        state = self._status_[name]
        for i in self._events_[name]:
            i(state)
