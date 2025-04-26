"""
#####################################
How this code works
#####################################
I split this up into functions that way our code is more modular. 
This just means that other files in the project can easily access the
data in the functions at any time of their convenience (think custom 
time limits in loops for different requirements).


Apart from that, nothing changed. The frequency at which everything is 
checked is now handled in the mosfet_control.py file since it just calls 
the functions in this file. 
"""



import spidev

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1350000

# === spidev functions expecting arguments in the following format ===

def read_adc(channel):
    if channel < 0 or channel > 7:
        raise ValueError("Channel must be 0–7")
    adc = spi.xfer2([1, (8 + channel) << 4, 0])
    return ((adc[1] & 3) << 8) + adc[2]

# === Voltage normalization ===

def conv_to_voltage(adc_val):
    return adc_val / 1023.0

# === This function is called by mosfet_control.c ===

def read_all_sensors():
    raw_temp = read_adc(2)
    raw_current = read_adc(3)
    raw_voltage = read_adc(0)

    voltage_temp = conv_to_voltage(raw_temp)
    voltage_current = conv_to_voltage(raw_current)
    voltage_voltage = conv_to_voltage(raw_voltage)

    temp_c = 100.0 * ((voltage_temp * 5.0) - 0.75) + 25.0
    current = ((voltage_current * 5.0 - 2.5) / 0.1375) - 1
    battery_voltage = voltage_voltage * 5.0

    return temp_c, current, battery_voltage
