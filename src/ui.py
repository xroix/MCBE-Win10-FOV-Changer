""" UI stuff, uses tkinter for the GUI 5"""
import webbrowser
import threading
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.font as tkf
from tkinter import simpledialog, messagebox

from PIL import Image, ImageTk

from run import VERSION
from src import exceptions
from src.processing import storage
from src.logger import Logger


def queue_alert_message(interface: dict, msg: str, *, warning=False):
    """ Add a alert message to the root thread queue
    :param interface: (dict) interface
    :param msg: (str) the message
    :param warning: (bool) if it is a warning
    :returns: (int) the time if it is a message
    """
    interface["RootThread"].queue.append(
        {"cmd": "alert", "params": ["msg", msg], "kwargs": {"warning": warning}, "wait": True})


def queue_ask_question(interface: dict, msg: str, title: str, callback):
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


def queue_quit_message(interface: dict, msg: str, title: str):
    """ Add a popup error to the root queue queue and then close the application (SystemTray.stopTray)
    :param interface: interface
    :param msg: (str) the message
    :param title: (str) the title
    :returns: (int) the time if it is a message
    """
    interface["RootThread"].queue.append(
        {"cmd": "alert", "params": ["popup", msg], "kwargs": {"ask": False, "title": title}, "wait": False,
         "callback": interface["SystemTray"].stop_tray})


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
        try:
            Logger.log("Root Thread", add=True)

            # Initialize root and start the queue update
            self.root = Root(self.interface)
            self.root.queue_update()

            # Start mainloop
            Logger.log("Root Gui", add=True)
            self.root.mainloop()
            Logger.log("Root Gui", add=False)

            Logger.log("Root Thread", add=False)

        # If something happens, log it
        except Exception as e:
            exceptions.handle(self.interface)


class Root(tk.Tk):
    """ The root window of the application
    """

    def __init__(self, interface):
        """ Initialize
        :param interface: interface
        """
        super().__init__()
        self.interface = interface

        self.storage = None

        # Setting up tk stuff
        self.title("FOV Changer")
        self.protocol("WM_DELETE_WINDOW", self.hide)
        self.resizable(False, False)
        self.geometry("800x400")
        self.tk.call('wm', 'iconphoto', self._w,
                     ImageTk.PhotoImage(Image.open(storage.find_file("logo.ico", meipass=True))))

        # Used inside the queue_update()
        self.rendered = False

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
        self.settings_frame = None
        self.log_frame = None
        self.log_text = None
        self.info_frame = None

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
            "space": None  # Space between features
        }

        # As long there isn't any content, show waiting cursor
        self.config(cursor="wait")

        # Add to interface
        self.interface.update({"Root": self})

    def hide(self):
        """ Hides the root (withdraws it)
        """
        self.withdraw()
        self.feature_edit_manager.hide_all()
        self.interface["Storage"].update_file()

    def queue_update(self):
        """ Run every 200 ms a new task from the queue
            E.g. {"cmd": "alert", "params":["msg", "hey"], "kwargs":{}, wait=True, callback=print}}
        """
        try:
            task = self.interface["RootThread"].queue.pop(0)

            # If it should wait to be rendered
            if "wait_for_render" in task and task["wait_for_render"] and not self.rendered:
                self.interface["RootThread"].queue.append(task)

                t = 0

            else:
                if "attr" not in task or task["attr"]:
                    t = getattr(self, task["cmd"])(*task["params"], **task["kwargs"])

                elif not task["attr"]:
                    t = task["cmd"](*task["params"], **task["kwargs"])

                else:
                    t = 0

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

        # Update logs
        if Logger.queue:
            Logger.write_all()

        self.after(500 + t, self.queue_update)

    def create_widgets(self):
        """ Create all widgets
            https://coolors.co/3a606e-607b7d-828e82-aaae8e-e0e0e0
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
        self.logo_image = ImageTk.PhotoImage(
            Image.open(storage.find_file("res\\logo-full.png", meipass=True)).resize((80, 80), Image.ANTIALIAS))
        tk.Label(header_frame, image=self.logo_image, borderwidth=0).pack(side="right", padx=3)

        # Title
        self.title_image = ImageTk.PhotoImage(
            Image.open(storage.find_file("res\\logo-title.png", meipass=True)).resize((280, 70), Image.ANTIALIAS))
        tk.Label(header_frame, image=self.title_image, borderwidth=0).pack(side="right", padx=6)

        # Notification
        self.notification_frame = tk.Frame(self.main_frame, bg="#E0E0E0", borderwidth=0)
        self.notification_label = tk.Label(self.notification_frame, bg="#E0E0E0", fg="#E0E0E0",
                                           textvariable=self.notification_message, font=(self.font, 14))

    def create_setup(self, callback: str):
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
            {"cmd": callback, "params": [self.setup_key_entry_var.get().strip()], "kwargs": {}}
        ))
        key_button.place(relx=.7, y=200, anchor="center")

        # Return to default cursor
        self.config(cursor="arrow")

    def create_content(self):
        """ Sub create from createWidgets, initializes the content
            Will also create notebook
        """
        # Add storage
        self.storage = self.interface["Storage"]

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
            {"cmd": "start_button_handle", "params": [e], "kwargs": {}}
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

        self.render_status(self.interface["Gateway"].status)

        # Separator
        tk.Frame(self.main_frame, bg="#3A606E").grid(column=2, row=1, sticky="WENS", ipadx=3)

        # Notebook
        self.create_notebook()

        # Return to default cursor
        self.config(cursor="arrow")

        # Update
        self.rendered = True

    def render_status(self, status: dict):
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

    def create_notebook(self):
        """ The notebook which contains settings and more is
            Gets execute in createContent
        """
        notebook = ttk.Notebook(self.main_frame, width=600, takefocus=False)
        notebook.grid(column=3, row=1, sticky="WENS", ipadx=0)

        # Create instances
        self.feature_frame = tk.Frame(notebook)
        self.settings_frame = tk.Frame(notebook)
        self.log_frame = tk.Frame(notebook)
        self.info_frame = tk.Frame(notebook)

        # Update to get height
        self.update()

        # Add them before to be then able to calculate the height
        notebook.add(self.feature_frame, text="Features")
        notebook.add(self.settings_frame, text="Settings")
        notebook.add(self.log_frame, text="Log")
        notebook.add(self.info_frame, text="Info")

        # Notebook Features
        # If there are features, render them
        if features := self.storage.features:
            self.create_tab_features(features)
            Logger.log("Rendered Features!")

        # or just make a placeholder
        else:
            self.feature_frame_placeholder = tk.Label(self.feature_frame,
                                                      text="Please start the FOV Changer once in order to"
                                                           " display the features!",
                                                      font=(self.font, 12), fg="#3A606E")
            self.feature_frame_placeholder.place(relx=.5, y=100, anchor="center")

        # Notebook Settings
        self.storage.settings_tk_vars = self.create_tab_settings()

        # Notebook Log
        self.create_tab_log()

        # Notebook Info
        self.create_tab_info()

    def create_tab_features(self, features):
        """ Creates the Tab features + tk_vars
            Own Method to make it better to read
        :param features: (Features) the features object
        """
        # Remove placeholder
        if self.feature_frame_placeholder:
            self.feature_frame_placeholder.place_forget()

        # Calculate y padding
        space = round((self.feature_frame.winfo_height() - tkf.Font(font=(self.font, 13)).metrics(
            "linespace") * features.len) / (features.len + 2))
        self.cache.update({"features_space": space})

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
            enable_button.bind("<Button-1>",
                               lambda e: self.on_feature_check_button(feature_id, _payload["enabled"].get()))
            enable_button.grid(column=extra_column, row=i, sticky="w", padx=30, pady=pad_y)
            _payload["enabled"].set(feature["enabled"] if feature["enabled"] is not None else False)

            # Entry for the key bind
            if not child:
                entry = ttk.Entry(self.feature_frame, font=(self.font, 12), justify="center",
                                  textvariable=_payload["key"])
                entry.grid(column=1, row=i, sticky="ew", padx=10, pady=pad_y)
                _payload["key"].set(feature["key"])

                # Validation
                proc = entry.register(lambda p: self.on_feature_entry_validate(feature_id, p))
                entry.configure(validate="key", validatecommand=(proc, "%P"))

            else:
                # We dont need it
                entry = None
                _payload["key"] = None

            # Edit Button
            edit_button_wrapper = tk.Frame(self.feature_frame, width=96, height=29, cursor="hand2")
            edit_button_wrapper.pack_propagate(0)
            edit_button = ttk.Button(edit_button_wrapper, text="Edit", takefocus=False)
            edit_button.bind("<Button-1>", lambda e: self.feature_edit_manager.open_feature(feature_id))
            edit_button.pack(fill="both")
            edit_button_wrapper.grid(column=2, row=i, sticky="w", padx=30, pady=pad_y)

            # If needed, disable
            if not feature["available"]:
                enable_button.state(["disabled"])
                edit_button.state(["disabled"])

                _payload["enabled"].set(False)

                if entry:
                    entry.state(["disabled"])

            else:
                # Top level for edit button
                self.feature_edit_manager.add_feature(feature_id, feature, _payload)

            # Help url
            url = tk.Label(self.feature_frame, text="?", font=(self.font, 13), fg="#3A606E", cursor="hand2")
            url.grid(column=3, row=i, sticky="w", padx=10, pady=pad_y)
            url.bind("<Button-1>", lambda e: webbrowser.open(self.storage.get("features_help_url").format(feature_id), new=2))

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
                        payload.update({child_key: render(features.data[child_key], child_key, i, child=True)})
                        done.add(child_key)

                        i += 1

        del done

        self.storage.features.tk_vars = payload

    def create_tab_settings(self):
        """ Displays the settings
        """
        settings = self.storage.get("settings")
        settings_url = self.storage.get("settings_help_url")

        # Calculate y padding
        length = len(settings) + 1
        space = round((self.feature_frame.winfo_height() - tkf.Font(font=(self.font, 13)).metrics(
            "linespace") * length) / (length + 2))

        def render(setting_name: str, setting_value: any, i: int):
            """ Render a setting
            :param setting_name: (str) name of setting
            :param setting_value: (any) value of setting
            :param i: (int) index
            """
            pad_y = space if i % 2 == 0 else 0

            tk_var = None

            # Text
            tk.Label(self.settings_frame, text=" ".join(x[0].upper() + x[1:] for x in setting_name.split("_")),
                     font=(self.font, 13)) \
                .grid(column=0, row=i, padx=30, pady=pad_y, sticky="e")

            # User input
            # Bool -> check button
            if isinstance(setting_value, bool):
                tk_var = tk.IntVar()

                setting_input = ttk.Checkbutton(self.settings_frame, takefocus=False, variable=tk_var)
                setting_input.grid(column=1, row=i, padx=10, pady=pad_y, sticky="w")

            # Else
            else:
                tk_var = tk.StringVar()

                setting_input = ttk.Entry(self.settings_frame, font=(self.font, 12), justify="left",
                                          textvariable=tk_var,
                                          takefocus=False)
                setting_input.grid(column=1, row=i, padx=10, pady=pad_y, sticky="w")

            tk_var.set(setting_value)

            # Help url
            url = tk.Label(self.settings_frame, text="?", font=(self.font, 13), fg="#3A606E", cursor="hand2")
            url.grid(column=3, row=i, sticky="e", padx=50, pady=space if i % 2 == 0 else 0)
            url.bind("<Button-1>", lambda e: webbrowser.open(settings_url.format(setting_name), new=2))

            return tk_var

        tk_vars = {}

        i = 0
        for name, value in settings.items():
            tk_vars.update({name: render(name, value, i)})
            i += 1

        # Create save button + help button
        save_button = ttk.Button(self.settings_frame, text="Save", takefocus=False,
                                 command=self.on_settings_save_button)
        save_button.grid(column=1, row=i, padx=10, pady=space if i % 2 == 0 else 0, sticky="ew")

        return tk_vars

    def create_tab_log(self):
        """ Creates the tab log, show logger messages
            Replacement for normal console
        """
        # "Border" for log messages
        inner_frame = tk.Frame(self.log_frame)
        inner_frame.pack(fill="both", padx=0, pady=20)

        # Scrollbar for text
        scrollbar = ttk.Scrollbar(inner_frame)
        scrollbar.pack(side="right", fill="y")

        # Log text
        self.log_text = tk.Text(inner_frame, height=400, yscrollcommand=scrollbar.set, relief="flat", borderwidth=12,
                                font=("Consolas", 13), bg="#121212", fg="#ffffff", state="disabled")
        self.log_text.pack(side="top", fill="y")

        scrollbar.config(command=self.log_text.yview)

    def create_tab_info(self):
        """ Provides information about the current version, author and more
        """
        tk.Label(self.info_frame, text="Made by XroixHD", font=(self.font, 13)) \
            .pack(padx=50, pady=30)

        ttk.Button(self.info_frame, text="GitHub", takefocus=False,
                   command=lambda: webbrowser.open("https://github.com/XroixHD", new=2)) \
            .pack(padx=50, pady=10)

        ttk.Button(self.info_frame, text="YouTube", takefocus=False,
                   command=lambda: webbrowser.open("https://www.youtube.com/channel/UC4dNeoE7POOYMelEV8w-zQg", new=2)) \
            .pack(padx=50, pady=0)

        ttk.Button(self.info_frame, text="Discord", takefocus=False,
                   command=lambda: webbrowser.open("https://discord.com/invite/fF3NKpM", new=2)) \
            .pack(padx=50, pady=10)

        tk.Label(self.info_frame, text=f"v{VERSION}", font=("Consolas", 13)) \
            .pack(padx=50, pady=10)

    def on_feature_entry_validate(self, feature_id: str, p: str):
        """ On validation of a feature key entry
        :param feature_id: (str) if of the feature
        :param p: (str) %P => content
        """
        # Cache
        if (p != "" and p == self.cache["validate"]) or len(p) > 1:
            self.bell()
            return False

        self.cache["validate"] = p

        # Change feature + prepare storage for update queue + register keys in listener new
        self.storage.features[feature_id]["key"] = p[0] if p else ""
        with self.storage.edited_lock:
            self.storage.edited = True

        with self.storage.listener_keys_edited_lock:
            self.storage.listener_keys_edited = True

        return True

    def on_feature_check_button(self, feature_id: str, state):
        """ On click of a feature check button
        :param feature_id: (str)  if of the feature
        :param state: state of the button
        """
        feature_value = self.storage.features[feature_id]

        if feature_value["available"]:

            # Reverse it because it's needed + save it
            feature_value["enabled"] = not state
            with self.storage.edited_lock:
                self.storage.edited = True

            # Update status
            if feature_value["name"] in self.interface["Gateway"].status:
                # print(bool(state if state else None))
                # print(state)
                # print(self.interface["Gateway"].status)
                # self.interface["Gateway"].status[feature_value["name"]] = state if state else None
                self.interface["ProcessingThread"].queue.append(
                    {"cmd": self.interface["Gateway"].status_check, "params": [], "kwargs": {}, "attr": False})

    def on_settings_save_button(self):
        """ Save settings
        """
        if self.storage.settings_tk_vars:
            settings = self.storage.get("settings")

            for name, value in self.storage.settings_tk_vars.items():
                try:
                    # Try to cast
                    value = type(settings[name])(value.get())

                    # Set new value
                    settings[name] = value

                except ValueError:
                    Logger.log(msg := f"Invalid value for {' '.join(x[0].upper() + x[1:] for x in name.split('_'))}")
                    queue_alert_message(self.interface, msg, warning=True)
                    return

            Logger.log("Saved new settings!")
            queue_alert_message(self.interface, "Saved new settings!")

        self.storage.update_file()

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
        self.storage = self.interface["Storage"]

        # TopLevels
        self.top_levels = {}

        # Fix bug
        self.open = False

    def position(self, feature_id):
        """ Position a top level
        :param feature_id: the id of the feature
        """
        self.top_levels[feature_id].geometry(f"300x150+{self.root.winfo_x()}+{self.root.winfo_y()}")

    def add_feature(self, feature_id: str, feature: dict, payload: dict):
        """ Add features
        :param feature_id: (str) the if of the feature
        :param feature: (dict) the feature
        :param payload: (dict) the payload
        """
        if feature_id not in self.top_levels:
            # Create Top Level
            top = tk.Toplevel(self.root)
            top.withdraw()
            top.title(feature["name"])
            top.tk.call('wm', 'iconphoto', top._w,
                        ImageTk.PhotoImage(Image.open(storage.find_file("logo.ico", meipass=True))))
            top.geometry(f"300x150+{self.root.winfo_x()}+{self.root.winfo_y()}")
            top.resizable(False, False)
            top.protocol("WM_DELETE_WINDOW", lambda: (self.hide(feature_id)))
            # top.bind("<Return>", lambda e: self.save(feature_id))

            # Content
            # tk.Label(top, text=feature["name"], font=(self.root.font, 18), fg="#3A606E")\
            #     .place(relx=.5, y=40, anchor="center")

            before = tk.StringVar()
            before.set(str(temp if (temp := feature["value"][0]) else ""))
            payload["value"].append(before)

            after = tk.StringVar()
            after.set(str(temp if (temp := feature["value"][1]) else ""))
            payload["value"].append(after)

            # Before
            before_wrapper = tk.Frame(top, height=29, width=70)
            before_wrapper.place(relx=.3, rely=.3, anchor="center")
            before_wrapper.pack_propagate(0)
            ttk.Entry(before_wrapper, font=(self.root.font, 12), justify="center",
                      textvariable=before) \
                .pack(fill="both")

            # Middle
            tk.Label(top, text="➞", font=(self.root.font, 25), fg="#3A606E") \
                .place(relx=.5, rely=.3, anchor="center")

            # After
            after_wrapper = tk.Frame(top, height=29, width=70)
            after_wrapper.place(relx=.7, rely=.3, anchor="center")
            after_wrapper.pack_propagate(0)
            ttk.Entry(after_wrapper, font=(self.root.font, 12), justify="center",
                      textvariable=after) \
                .pack(fill="both")

            # Save
            save_button_wrapper = tk.Frame(top, width=110, height=29)
            save_button_wrapper.pack_propagate(0)
            ttk.Button(save_button_wrapper, text="Save", takefocus=False,
                       command=lambda: self.save(feature_id)).pack(fill="both")
            save_button_wrapper.place(relx=.5, rely=.7, anchor="center")

            # Add it
            self.top_levels.update({feature_id: top})

    def open_feature(self, feature_id: str):
        """ Open a specific feature top level
        :param feature_id: the if of the feature
        """
        if not self.open and self.storage.features[feature_id]["available"]:
            self.top_levels[feature_id].deiconify()
            self.top_levels[feature_id].grab_set()
            self.position(feature_id)

            self.open = True

    def save(self, feature_id: str):
        """ Click event for save button
        :param feature_id: the id of the feature
        """
        if self.open:
            # Hide window
            self.top_levels[feature_id].withdraw()
            self.top_levels[feature_id].grab_release()

            # Get some values to clean up code
            feature = self.storage.features[feature_id]
            tk_var = self.storage.features.tk_vars[feature_id]["value"]
            presets = self.storage.features.presets[feature_id]

            values = [x.get() for x in tk_var]

            # Save new values into the real value field and check type
            # Also translate the value if needed
            if self.storage.features.check_value(self.storage.features, feature_id, feature, override_value=values):
                feature["value"] = values
                self.interface["Storage"].update_file()

                Logger.log(f"Saved new values! [{' -> '.join(values)}]")
                # queue_alert_message(self.interface, "Saved new values!")

            # Reset from real saved value
            else:
                Logger.log(f"Invalid value entered! [{' -> '.join(values)}]")
                queue_alert_message(self.interface, "Invalid value entered!", warning=True)
                tk_var[0].set(str(temp if (temp := feature["value"][0]) else ""))
                tk_var[1].set(str(temp if (temp := feature["value"][1]) else ""))

            self.open = False

    def hide(self, feature_id: str):
        """ Hide a top level, like save() but without saving stuff
        :param feature_id: the id of the feature
        """
        if self.open:
            # Hide window
            self.top_levels[feature_id].withdraw()
            self.top_levels[feature_id].grab_release()

            self.open = False

    def hide_all(self):
        """ Hides / Withdraws all top levels
        """
        for top_level_obj in self.top_levels.values():
            top_level_obj.withdraw()
            top_level_obj.grab_release()
