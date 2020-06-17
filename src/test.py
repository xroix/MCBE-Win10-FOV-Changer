import tkinter as tk


root = tk.Tk()

variable = tk.StringVar()
variable.set("Drück mich")

button = tk.Button(root, textvariable=variable, command=lambda: variable.set("Stop"))
button.pack(padx=40, pady=40)

root.mainloop()
