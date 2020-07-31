import threading
import time
import tkinter as tk


def schedule(seconds=1):
    print("1")

    def decorator(f):
        """ Save method
        """

        print("2")
        return f

    return decorator


class A:
    @schedule(seconds=20)
    def test(self):
        print("Test method got exec")
        return "success"


print("Test method output: ", A().test())
