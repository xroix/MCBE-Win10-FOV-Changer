DEBUG = True


def logDebug(msg: str, *, add=None):
    """ Debug logs a message
    :param add: if it is + or -
    :param msg: the message
    """
    if add:
        print(f"+ {msg}")

    # Cant use not because none is also "false"
    elif add is False:
        print(f"- {msg}")

    else:
        print(f"> {msg}")
