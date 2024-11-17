import tkinter as tk
import threading
import time

class App:
    def __init__(self, root):
        self.root = root
        self.root.geometry("1200x400")
        self.root.title("BMS UI")

        #Setting uo geometry for the tkinter window. 
        #Tkinter windows are rows and columns
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_rowconfigure(2, weight=1)
        self.root.grid_rowconfigure(3, weight=1)
        self.root.grid_rowconfigure(4, weight=1)

        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        label_font = ("Helvetica", 36)
        value_font = ("Helvetica", 36)

        #All this is just the values and their labels that will be updated later
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

        self.charge_label = tk.Label(root, text="Charge", font=label_font, anchor="e")
        self.charge_label.grid(row=3, column=0, padx=10, pady=10, sticky="e")
        self.charge_value = tk.Entry(root, font=value_font, bd=0, state='readonly', readonlybackground=self.root.cget("bg"))
        self.charge_value.grid(row=3, column=1, padx=10, pady=10, sticky="w")

        self.status_label = tk.Label(root, text="Status", font=label_font, anchor="e")
        self.status_label.grid(row=4, column=0, padx=10, pady=10, sticky="e")
        self.status_value = tk.Entry(root, font=value_font, bd=0, state='readonly', readonlybackground=self.root.cget("bg"))
        self.status_value.grid(row=4, column=1, padx=10, pady=10, sticky="w")

        #This is called in a forever wjile loop every second
        self.update_values()

        #Python function that converts any number base to int. In our case hex -> int
    def RS485_to_decimal(self, data):
        
        try:
            return int(data, 16)
        except Exception as e:
            print("Error: Invlaid hexacimal value")
            return None
    #This just writes to the BMS.txt file so the charger can read from it
    def write_to_BMS_file(self, message):
        with open('from_BMS.txt', 'a') as bms_file:
            bms_file.write(message + '\n')

    def update_values(self):
        try:
            with open('from_Charger.txt', 'r') as file:
                lines = file.readlines()
                if lines:
                    #Starts at the last line of the file and ignores whitespace. It chunks 2 bytes
                    last_line = lines[-1].strip().split()

                    if last_line[0] == "01":
                        raw_voltage = last_line[1]
                        raw_current = last_line[2]
                        raw_temperature = last_line[3]
                        raw_charge = last_line[4]
                        raw_status = last_line[5]

                        voltage = self.RS485_to_decimal(raw_voltage)
                        current = self.RS485_to_decimal(raw_current)
                        temperature = self.RS485_to_decimal(raw_temperature)
                        charge = self.RS485_to_decimal(raw_charge)
                        status = "Charging" if raw_status == "00" else "Discharging"

                        self.voltage_value.configure(state='normal')
                        self.voltage_value.delete(0, tk.END)
                        self.voltage_value.insert(0, str(voltage) + "V")
                        self.voltage_value.configure(state='readonly')

                        self.current_value.configure(state='normal')
                        self.current_value.delete(0, tk.END)
                        self.current_value.insert(0, str(current) + "A")
                        self.current_value.configure(state='readonly')

                        self.temperature_value.configure(state='normal')
                        self.temperature_value.delete(0, tk.END)
                        self.temperature_value.insert(0, str(temperature) + " Degrees")
                        self.temperature_value.configure(state='readonly')

                        self.charge_value.configure(state='normal')
                        self.charge_value.delete(0, tk.END)
                        self.charge_value.insert(0, str(charge) + "%")
                        self.charge_value.configure(state='readonly')

                        self.status_value.configure(state='normal')
                        self.status_value.delete(0, tk.END)
                        self.status_value.insert(0, status)
                        self.status_value.configure(state='readonly')

                        #Thresholds for values. We cna make these whatever we want
                        if voltage and voltage > 200:
                            self.write_to_BMS_file("02 01 11")
                            print("Voltage exceeded 200. Sending message to charger")
                        elif current and current > 50:
                            self.write_to_BMS_file("02 02 11")
                            print("Current exceeded 50. Sending message to charger")
                        elif temperature and temperature > 200:
                            self.write_to_BMS_file("02 03 11")
                            print("Temperature exceeded 200. Sending message to charger")
                        elif charge and charge > 99:
                            self.write_to_BMS_file("02 11 00")
                            print("Charge exceeded 100. Telling charger to reverse direction")
                        else:
                            self.write_to_BMS_file("02 00 00")
                            print("All values are stable. Continue")

        except Exception as e:
            print(f"Error reading file: {e}")

        self.root.after(1000, self.update_values)

#Runs forever
while(1):
    root = tk.Tk()
    app = App(root)
    root.mainloop()
