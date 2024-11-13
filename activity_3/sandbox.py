from tkinter import *
import os

print("Current working directory:", os.getcwd())

root = Tk()
root.geometry("500x300")
root.title("Command Line Display")
root.configure(bg="black")

input_file = "input_text.txt"

label = Label(root, text="Waiting for input...", font=("Helvetica", 20), fg="white", bg="black")
label.pack(expand=True)

last_text = ""

def check_for_update():
    global last_text
    try:
        if os.path.exists(input_file):
            with open(input_file, "r") as file:
                new_text = file.readline().strip()
                print(f"Read from file: '{new_text}'")
                if new_text and new_text != last_text:
                    label.config(text=new_text)
                    last_text = new_text
                    print(f"Updated to: '{new_text}'")
                elif not new_text:
                    print("No new input found in file")
        else:
            print(f"File '{input_file}' doen't exist")
    except Exception as e:
        print(f"Error reading the file: {e}")

    root.after(1000, check_for_update)

check_for_update()
root.mainloop()
