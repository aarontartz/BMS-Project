import tkinter as tk
import threading
import time

class App:
    def __init__(self, root):
        self.root = root
        self.root.geometry("1200x400")
        self.root.title("Charger UI")

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        label_font = ("Helvetica", 36)
        value_font = ("Helvetica", 36)

        self.message_label = tk.Label(root, text="BMS Message", font=label_font, anchor="e")
        self.message_label.grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.message_value = tk.Entry(root, font=value_font, bd=0, state='readonly', readonlybackground=self.root.cget("bg"))
        self.message_value.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        self.status_label = tk.Label(root, text="Status", font=label_font, anchor="e")
        self.status_label.grid(row=1, column=0, padx=10, pady=10, sticky="e")
        self.status_value = tk.Entry(root, font=value_font, bd=0, state='readonly', readonlybackground=self.root.cget("bg"))
        self.status_value.grid(row=1, column=1, padx=10, pady=10, sticky="w")

        self.update_values()

    def update_values(self):
        try:
            with open('from_BMS.txt', 'r') as file:
                lines = file.readlines()
                if lines:
                    last_line = lines[-1].strip().split()

                    if last_line[0] == "02":
                        message = last_line[1]
                        raw_status = last_line[2]

                        if message == "00":
                            BMS_message = "Stable, Continue"
                        elif message == "01":
                            BMS_message = "ERROR: Over Voltage"
                        elif message == "02":
                            BMS_message = "ERROR: Current Too High"
                        elif message == "03":
                            BMS_message = "ERROR: Temperature Too High"
                        elif message == "11":
                            BMS_message = "Reverse Direction"
                        
                        if raw_status == "00":
                            status = "Stable"
                        else:
                            status = "Critical"

                        self.message_value.configure(state='normal')
                        self.message_value.delete(0, tk.END)
                        self.message_value.insert(0, BMS_message)
                        self.message_value.configure(state='readonly')

                        self.status_value.configure(state='normal')
                        self.status_value.delete(0, tk.END)
                        self.status_value.insert(0, status)
                        self.status_value.configure(state='readonly')

        except Exception as e:
            print(f"Error reading file: {e}")

        self.root.after(1000, self.update_values)

while(1):
    root = tk.Tk()
    app = App(root)
    root.mainloop()
