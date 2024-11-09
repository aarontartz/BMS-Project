from tkinter import *
import random

'''
ATM this is just generating random data and updating the display every 10 seconds. Currently working
on integrating command line inputs to update the display. The buttons are just placeholders for now.
'''

root = Tk()
root.geometry("1000x1000")
root.configure(bg="black")

def sum_function(a, b):
    return a + b

def update_label():
    a = random.randint(1, 100)
    b = random.randint(1, 100)
    result = sum_function(a, b)
    label.config(text=f"Voltage: {result}V")
    root.after(10000, update_label)

label = Label(root, text="Voltage: ", font=("Helvetica", 30), fg="white", bg="black")
label.place(relx=0.5, rely=0.5, anchor=CENTER)

def product_function(a, b):
    return a * b

def update_product_label():
    a = random.randint(1, 100)
    b = random.randint(1, 100)
    result = product_function(a, b)
    product_label.config(text=f"Power: {result}W")
    root.after(10000, update_product_label)

product_label = Label(root, text="Power: ", font=("Helvetica", 30), fg="white", bg="black")
product_label.place(relx=0.5, rely=0.6, anchor=CENTER)

update_label()
update_product_label()

def create_oval_button(text, command, bg, fg):
    button = Button(root, text=text, command=command, bg=bg, fg=fg, font=("Helvetica", 20), relief=FLAT)
    button.place(relx=0.9, rely=0.1 if text == "Read" else 0.2, anchor=NE)
    return button

def read_action():
    print("Read button clicked")

def write_action():
    print("Write button clicked")

read_button = create_oval_button("Read", read_action, "white", "blue")
write_button = create_oval_button("Write", write_action, "blue", "white")

root.mainloop()
