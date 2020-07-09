""" UI stuff, uses tkinter for the GUI 5"""

import webbrowser
import threading
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.font as tkf
from tkinter import simpledialog, messagebox

from PIL import Image, ImageTk

from src import logger


def queueAlertMessage(interface: dict, msg: str, *, warning=False):
    """ Add a alert message to the root thread queue
    :param interface: (dict) interface
    :param msg: (str) the message
    :param warning: (bool) if it is a warning
    :returns: (int) the time if it is a message
    """
    interface["RootThread"].queue.append(
        {"cmd": "alert", "params": ["msg", msg], "kwargs": {"warning": warning}, "wait": True})


def queueAskQuestion(interface: dict, msg: str, title: str, callback):
    """ Add a popup message to the root thread queue
    :param interface: (dict) interface
    :param msg: (str) the message
    :param title: (str) the title
    :param callback: the callback function
    :returns: (int) the time if it is a message
    """
    interface["RootThread"].queue.append(
        {"cmd": "alert", "params": ["popup", msg], "kwargs": {"ask": True, "title": title}, "wait": True,
         "callback": callback})


def queueQuitMessage(interface: dict, msg: str, title: str):
    """ Add a popup error to the root queue queue and then close the application (SystemTray.stopTray)
    :param interface: interface
    :param msg: (str) the message
    :param title: (str) the title
    :returns: (int) the time if it is a message
    """
    interface["RootThread"].queue.append(
        {"cmd": "alert", "params": ["popup", msg], "kwargs": {"ask": False, "title": title}, "wait": False,
         "callback": interface["SystemTray"].stopTray})


class RootThread(threading.Thread):
    """ The thread for the gui (tkinter)
    """

    def __init__(self, interface: dict):
        """ Initialize
        :param interface: interface
        """
        super().__init__(name=self.__class__.__name__)
        self.interface = interface

        # Queue for executing methods inside the thread
        self.queue = []

        # The root window (tkinter.TK)
        self.root = None

        # Add thread to interface
        self.interface.update({"RootThread": self})

    def run(self) -> None:
        """ Run method of thread
        """
        logger.logDebug("Root Thread", add=True)

        # Initialize root and start the queue update
        self.root = Root(self.interface)
        self.root.queueUpdate()

        # Start mainloop
        logger.logDebug("Root Gui", add=True)
        self.root.mainloop()
        logger.logDebug("Root Gui", add=False)

        logger.logDebug("Root Thread", add=False)


class Root(tk.Tk):
    """ The root window of the application
    """

    def __init__(self, interface):
        """ Initialize
        :param interface: interface
        """
        super().__init__()
        self.interface = interface

        # Setting up tk stuff
        self.title("FOV Changer")
        self.protocol("WM_DELETE_WINDOW", self.withdraw)
        self.resizable(False, False)
        self.geometry("800x400")
        self.tk.call('wm', 'iconphoto', self._w, ImageTk.PhotoImage(Image.open("logo.ico")))

        # Ttk style
        self.style = ttk.Style()
        self.font = "Sans Serif"

        # Widgets whose reference are needed
        self.main_frame = None
        self.setup_frame = None
        self.status_frame = None
        self.feature_frame = None
        self.feature_frame_placeholder = None
        self.start_button = None

        # TextVariables
        self.start_button_var = tk.StringVar()
        self.start_button_var.set("Start")
        self.setup_key_entry_var = tk.StringVar()

        # Images
        self.logo_image = None
        self.title_image = None

        # Message System
        self.notification_frame = None
        self.notification_label = None
        self.notification_message = tk.StringVar()

        # TopLevels
        self.feature_edit_manager = FeatureEditManager(self.interface, self)

        # Cache
        self.cache = {
            "validate": "",  # On entry key validate
            "space": None   # Space between features
        }

        # Todo delete
        self.var = None

        # Add to interface
        self.interface.update({"Root": self})

    def queueUpdate(self):
        """ Run every 200 ms a new task from the queue
            E.g. {"cmd": "alert", "params":["msg", "hey"], "kwargs":{}, wait=True, callback=print}}
        """
        try:
            task = self.interface["RootThread"].queue.pop(0)
            t = getattr(self, task["cmd"])(*task["params"], **task["kwargs"])

            # If there is no wait
            if "wait" not in task or not task["wait"]:
                t = 0

            # Check if there is a callback
            if "callback" in task:
                task["callback"](t)

        except IndexError:
            # No tasks
            t = 0

        # Check return value
        if not isinstance(t, int):
            t = 2500

        self.after(500 + t, self.queueUpdate)

    def createWidgets(self, content: bool):
        """ Create all widgets
            https://coolors.co/3a606e-607b7d-828e82-aaae8e-e0e0e0
        :param content: (bool) if content should be created
        """
        # Create style
        # Thanks to https://stackoverflow.com/a/23399786/11940809 and more
        # Remove Focus outline from Tab
        self.style.layout("Tab", [('Notebook.tab', {'sticky': 'nswe', 'children': [('Notebook.padding',
                                                                                    {'side': 'top', 'sticky': 'nswe',
                                                                                     'children': [('Notebook.label',
                                                                                                   {'side': 'top',
                                                                                                    'sticky': ''})]})]})])
        self.style.configure("Tab", padding=[50, 4], font=(self.font, 12))
        self.style.configure("TCheckbutton", font=(self.font, 13))
        self.style.configure("TEntry", padding=[10, 2, 10, 2])
        self.style.configure("TButton", font=(self.font, 12), padding=[30, 2, 30, 2])

        # Main frame
        self.main_frame = tk.Frame(self, bg="#E0E0E0")
        self.main_frame.pack(fill="both", expand=True)
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.rowconfigure(1, weight=1)

        # The header frame is located above the content
        header_frame = tk.Frame(self.main_frame, bg="#3A606E")
        header_frame.grid(column=0, row=0, columnspan=4, sticky="WE")

        # Logo
        self.logo_image = ImageTk.PhotoImage(Image.open("res\\logo-full.png").resize((80, 80), Image.ANTIALIAS))
        tk.Label(header_frame, image=self.logo_image, borderwidth=0).pack(side="right", padx=3)

        # Title
        self.title_image = ImageTk.PhotoImage(Image.open("res\\logo-title.png").resize((280, 70), Image.ANTIALIAS))
        tk.Label(header_frame, image=self.title_image, borderwidth=0).pack(side="right", padx=6)

        # Notification
        self.notification_frame = tk.Frame(self.main_frame, bg="#E0E0E0", borderwidth=0)
        self.notification_label = tk.Label(self.notification_frame, bg="#E0E0E0", fg="#E0E0E0",
                                           textvariable=self.notification_message, font=(self.font, 14))

    def createSetup(self, callback: str):
        """ Create the setup for asking the user for the license (AUTHENTICATION)
        :param callback: (str) method name which gets added to the processing queue
        """
        self.setup_frame = tk.Frame(self.main_frame, bg="#E0E0E0")
        self.setup_frame.grid(column=1, row=1, sticky="WENS")

        tk.Label(self.setup_frame, text="Please enter your license key to prove your beta access.", bg="#E0E0E0",
                 font=(self.font, 12)) \
            .place(relx=.5, y=120, anchor="center")

        key_entry = ttk.Entry(self.setup_frame, font=(self.font, 12), justify="center",
                              textvariable=self.setup_key_entry_var, width=30)
        key_entry.place(relx=.4, y=200, anchor="center")

        key_button = ttk.Button(self.setup_frame, text="Authenticate", takefocus=False)
        key_button.bind("<Button-1>", lambda e: self.interface["ProcessingThread"].queue.append(
            {"cmd": callback, "params": [self.setup_key_entry_var.get()], "kwargs": {}}
        ))
        key_button.place(relx=.7, y=200, anchor="center")

    def createContent(self):
        """ Sub create from createWidgets, initializes the content
            Will also create notebook
        """
        # Destroy old frame
        if self.setup_frame:
            self.setup_frame.destroy()

        # Control dashboard
        control_frame = tk.Frame(self.main_frame, bg="#E0E0E0")
        control_frame.grid(column=0, row=1, sticky="WENS")

        # Start button
        start_button_wrapper = tk.Frame(control_frame, width=200, highlightbackground="#3A606E", highlightthickness=2,
                                        cursor="hand2")
        self.start_button = tk.Button(start_button_wrapper, text="", font=(self.font, 11),
                                      takefocus=False, relief="flat", borderwidth=0, textvariable=self.start_button_var)
        start_button_cmd = lambda e: self.interface["ProcessingThread"].queue.append(
            {"cmd": "startButtonHandle", "params": [e], "kwargs": {}}
        )
        self.start_button.bind("<Button-1>", start_button_cmd)
        self.bind("<Return>", start_button_cmd)
        self.start_button.pack(fill="both")
        start_button_wrapper.grid(column=0, row=0, sticky="ew", padx=20, pady=25)

        # Status
        self.status_frame = tk.Frame(control_frame, width=128,
                                     bg="#f0f0f0", highlightbackground="#3A606E", highlightthickness=2)
        self.status_frame.grid(column=0, row=1, padx=20, pady=0, ipadx=10)
        self.status_frame.columnconfigure(1, weight=1)
        self.status_frame.rowconfigure(1, weight=1)

        self.renderStatus(self.interface["Gateway"].status)

        # Separator
        tk.Frame(self.main_frame, bg="#3A606E").grid(column=2, row=1, sticky="WENS", ipadx=3)

        # Notebook
        self.createNotebook()

    def renderStatus(self, status: dict):
        """ Render a status
        :param status: the status
        """
        for child in self.status_frame.winfo_children():
            child.destroy()

        symbols = {True: "✔️", False: "❌", None: "⭕"}
        colors = {True: "#19b33d", False: "#eb4034", None: "#3A606E"}

        for x, (name, state) in enumerate(status.items()):
            s = tk.Label(self.status_frame, text=symbols[state], font=(self.font, 11),
                         fg=colors[state],
                         bg="#f0f0f0")
            s.grid(column=0, row=x, sticky="e", ipadx=10, ipady=10)

            t = tk.Label(self.status_frame, text=name, font=(self.font, 11), bg="#f0f0f0")
            t.grid(column=1, row=x, sticky="w", ipadx=0, ipady=10)

        self.update()

    def createNotebook(self):
        """ The notebook which contains settings and more is inside the content
            Gets execute in createContent
        """
        notebook = ttk.Notebook(self.main_frame, width=600, takefocus=False)
        notebook.grid(column=3, row=1, sticky="WENS", ipadx=0)

        # Create instances
        self.feature_frame = tk.Frame(notebook)
        settings_frame = tk.Frame(notebook)
        log_frame = tk.Frame(notebook)
        help_frame = tk.Frame(notebook)

        # Update to get height
        self.update()

        # Add them before to be then able to calculate the height
        notebook.add(self.feature_frame, text="Features")
        notebook.add(settings_frame, text="Settings")
        notebook.add(log_frame, text="Log")
        notebook.add(help_frame, text="Info")

        # If there are features, render them
        if features := self.interface["Storage"].features:
            self.interface["Storage"].features.tk_vars = self.createTabFeature(features)
            logger.logDebug("Rendered Features!")

        # or just make a placeholder
        else:
            self.feature_frame_placeholder = tk.Label(self.feature_frame,
                                                      text="Please start the FOV Changer once in order to"
                                                           " display the features!",
                                                      font=(self.font, 12), fg="#3A606E")
            self.feature_frame_placeholder.place(relx=.5, y=100, anchor="center")

    def createTabFeature(self, features) -> dict:
        """ Creates the Tab feature
            Own Method to make it better to read
        :param features: (Features) the features object
        :returns: (dict) payload with the tk variables
        """
        # Remove placeholder
        if self.feature_frame_placeholder:
            self.feature_frame_placeholder.place_forget()

        # Calculate y padding, if cached, then use cached
        if "space" in self.cache and self.cache["space"]:
            space = self.cache["space"]

        else:
            space = round((self.feature_frame.winfo_height() - tkf.Font(font=(self.font, 13)).metrics(
                "linespace") * features.len) / (features.len + 2))
            self.cache.update({"space": space})

        # Vars for return
        payload = {}

        def render(feature: dict, feature_id: str, i: int, *, child=False):
            """ Render function for better organisation
            :param feature: (dict) feature
            :param feature_id: the if of the feature
            :param i: (int) index
            :param child: if it is a child
            """
            # Padding
            pad_y = space if i % 2 == 0 else 0
            extra_column = int(child)

            # Payload which gets merged into the main payload
            _payload = {"enabled": tk.IntVar(), "key": tk.StringVar(), "value": []}

            # Enable Button + Label
            enable_button = ttk.Checkbutton(self.feature_frame, text=f"   {feature['name']}",
                                            variable=_payload["enabled"], cursor="hand2")
            enable_button.grid(column=extra_column, row=i, sticky="w", padx=30, pady=pad_y)
            _payload["enabled"].set(feature["enabled"])

            # Entry for the key bind
            if not child:
                entry = ttk.Entry(self.feature_frame, font=(self.font, 12), justify="center",
                                  textvariable=_payload["key"])
                entry.grid(column=1, row=i, sticky="ew", padx=10, pady=pad_y)
                _payload["key"].set(feature["key"])

                # Validation
                proc = entry.register(lambda p: self.onFeatureValidate(feature_id, p))
                entry.configure(validate="key", validatecommand=(proc, "%P"))

            else:
                # We dont need it
                entry = None
                _payload["key"] = None

            # Edit Button
            edit_button_wrapper = tk.Frame(self.feature_frame, width=96, height=29)
            edit_button_wrapper.pack_propagate(0)
            edit_button = ttk.Button(edit_button_wrapper, text="Edit", takefocus=False)
            edit_button.bind("<Button-1>", lambda e: self.feature_edit_manager.openFeature(feature_id))
            edit_button.pack(fill="both")
            edit_button_wrapper.grid(column=2, row=i, sticky="w", padx=30, pady=pad_y)
            
            self.feature_edit_manager.addFeature(feature_id, feature)

            # If needed, disable
            if not feature["available"]:
                enable_button.state(["disabled"])

                if entry:
                    entry.state(["disabled"])

            # Help url
            url = tk.Label(self.feature_frame, text="?", font=(self.font, 13), fg="#3A606E", cursor="hand2")
            url.grid(column=3, row=i, sticky="w", padx=10, pady=pad_y)
            url.bind("<Button-1>", lambda e: webbrowser.open(feature["help"], new=2))

            return _payload

        # Iter through features
        i = 0
        done = set()
        for key, f in features.data.items():
            if key not in done:
                payload.update({key: render(f, key, i)})
                done.add(key)

                i += 1

                # Create each child
                if f["children"]:
                    for child_key in f["children"]:
                        payload.update({key: render(features.data[child_key], child_key, i, child=True)})
                        done.add(child_key)

                        i += 1

        return payload

    def onFeatureValidate(self, feature_id, p):
        """ On validation of a feature key entry
        :param feature_id: if of the feature
        :param p: %P => content
        """
        # Cache
        if p == self.cache["validate"]:
            self.bell()
            return False

        self.cache["validate"] = p

        # TODO Save
        print(p, "TODO")

        # Validation
        if len(p) > 1:
            self.bell()
            return False

        else:
            return True

    def alert(self, mode: str, msg: str, *, warning=False, ask=False, title="Untitled") -> any:
        """ Alert a message or a popup
        :param mode: (str) either 'popup' or 'msg', falls back to msg
        :param msg: (str) the message
        :param warning: (bool) if it is a warning
        :param ask: (bool) if a popup should ask
        :param title: (str) the title of a popup
        :returns: (int) the time if it is a message
        """
        # Pop ups
        if mode.lower() == "popup":
            if ask:
                return simpledialog.askstring(title=title, prompt=msg)

            else:
                return messagebox.showerror(title=title, message=msg)

        # A message, display at footer
        else:
            # Change color
            if warning:
                self.notification_frame["bg"] = "#eb4034"
                self.notification_label["bg"] = "#eb4034"

            else:
                self.notification_frame["bg"] = "#3A606E"
                self.notification_label["bg"] = "#3A606E"

            # Set message
            self.notification_message.set(msg)

            # Pack and grid it
            self.notification_frame.grid(column=0, row=2, columnspan=4, sticky="WE", padx=0, pady=0)
            self.notification_label.pack(padx=5, pady=5)
            self.update()

            # And the invoke, time is calculate with 'round(len(msg) / 5 / 180 * 60 * 4) * 1000'
            # However, to speed up, it used the rough 'len(msg) * 266'
            self.after((n := len(msg) * 266),
                       lambda: (self.notification_label.pack_forget(), self.notification_frame.grid_forget()))

            return n


class FeatureEditManager:
    """ Manages the feature edit top levels
    """

    def __init__(self, interface: dict, root: tk.Tk):
        """ Initialize
        :param interface: the interface
        :param root: the root
        """
        # Settings
        self.interface = interface
        self.root = root

        # TopLevels
        self.top_levels = {}
        self.top_levels_vars = {}

    def position(self, feature_id):
        """ Position a top level
        :param feature_id: the id of the feature
        """
        self.top_levels[feature_id].geometry(f"300x150+{self.root.winfo_x()}+{self.root.winfo_y()}")

    def addFeature(self, feature_id: str, feature: dict):
        """ Add features
        :param feature_id: the if of the feature
        :param feature: the feature
        """
        if feature_id not in self.top_levels:
            # Create Top Level
            top = tk.Toplevel(self.root)
            top.withdraw()
            top.title(feature["name"])
            top.tk.call('wm', 'iconphoto', top._w, ImageTk.PhotoImage(Image.open("logo.ico")))
            top.geometry(f"300x150+{self.root.winfo_x()}+{self.root.winfo_y()}")
            top.resizable(False, False)

            # Content
            # tk.Label(top, text=feature["name"], font=(self.root.font, 18), fg="#3A606E")\
            #     .place(relx=.5, y=40, anchor="center")

            before = tk.StringVar()
            before.set("test")
            after = tk.StringVar()
            after.set("test")

            # Before
            before_wrapper = tk.Frame(top, height=29, width=70)
            before_wrapper.place(relx=.3, rely=.3, anchor="center")
            before_wrapper.pack_propagate(0)
            ttk.Entry(before_wrapper, font=(self.root.font, 12), justify="center",
                      textvariable=before)\
                .pack(fill="both")

            # Middle
            tk.Label(top, text="➞", font=(self.root.font, 25), fg="#3A606E") \
                .place(relx=.5, rely=.3, anchor="center")

            # After
            after_wrapper = tk.Frame(top, height=29, width=70)
            after_wrapper.place(relx=.7, rely=.3, anchor="center")
            after_wrapper.pack_propagate(0)
            ttk.Entry(after_wrapper, font=(self.root.font, 12), justify="center")\
                .pack(fill="both")

            # Save
            save_button_wrapper = tk.Frame(top, width=110, height=29)
            save_button_wrapper.pack_propagate(0)
            ttk.Button(save_button_wrapper, text="Save", takefocus=False,
                       command=lambda: self.save(feature_id)).pack(fill="both")
            save_button_wrapper.place(relx=.5, rely=.7, anchor="center")

            # Add it
            self.top_levels.update({feature_id: top})
            self.top_levels_vars.update({feature_id: {"before": before, "after": after}})

    def openFeature(self, feature_id: str):
        """ Open a specific feature top level
        :param feature_id: the if of the feature
        """
        self.top_levels[feature_id].deiconify()

    def save(self, feature_id: str):
        """ Click event for save button
        :param feature_id: the id of the feature
        """
        # Hide window
        self.top_levels[feature_id].withdraw()

        # Save new values
        # self.interface["Storage"].get("value")


class FeatureEditTopLevel(tk.Toplevel):
    """ The top level for a feature edit
    """

    def __init__(self):
        """ Initialize
        """
        super().__init__()
        self.title()
