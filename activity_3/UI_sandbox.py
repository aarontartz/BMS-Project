import tkinter as tk
import threading
import time

class App:
    def __init__(self, root):
        self.root = root
        self.root.geometry("1200x300")
        self.root.title("Voltage and Current Monitor")

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_rowconfigure(2, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        label_font = ("Helvetica", 36)
        value_font = ("Helvetica", 36)

        self.voltage_label = tk.Label(root, text="Voltage", font=label_font, anchor="e")
        self.voltage_label.grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.voltage_value = tk.Entry(root, font=value_font, bd=0, state='readonly', readonlybackground=self.root.cget("bg"))
        self.voltage_value.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        self.current_label = tk.Label(root, text="Current", font=label_font, anchor="e")
        self.current_label.grid(row=1, column=0, padx=10, pady=10, sticky="e")
        self.current_value = tk.Entry(root, font=value_font, bd=0, state='readonly', readonlybackground=self.root.cget("bg"))
        self.current_value.grid(row=1, column=1, padx=10, pady=10, sticky="w")

        self.temperature_label = tk.Label(root, text="Temperature", font=label_font, anchor="e")
        self.temperature_label.grid(row=2, column=0, padx=10, pady=10, sticky="e")
        self.temperature_value = tk.Entry(root, font=value_font, bd=0, state='readonly', readonlybackground=self.root.cget("bg"))
        self.temperature_value.grid(row=2, column=1, padx=10, pady=10, sticky="w")

        self.update_values()

    def update_values(self):
        try:
            with open('input_text.txt', 'r') as file:
                lines = file.readlines()
                if lines:
                    last_line = lines[-1].strip().split()
                    voltage = last_line[0]
                    current = last_line[1]
                    temperature = last_line[2]

                    self.voltage_value.configure(state='normal')
                    self.voltage_value.delete(0, tk.END)
                    self.voltage_value.insert(0, voltage + " V")
                    self.voltage_value.configure(state='readonly')

                    self.current_value.configure(state='normal')
                    self.current_value.delete(0, tk.END)
                    self.current_value.insert(0, current + " A")
                    self.current_value.configure(state='readonly')

                    self.temperature_value.configure(state='normal')
                    self.temperature_value.delete(0, tk.END)
                    self.temperature_value.insert(0, temperature + " Degrees")
                    self.temperature_value.configure(state='readonly')
        except Exception as e:
            print(f"Error reading file: {e}")

        self.root.after(1000, self.update_values)

while(1):
    root = tk.Tk()
    app = App(root)
    root.mainloop()
