import threading

# SPI setup
spi = spidev.SpiDev()
spi.open(0, 0) # bus 0, device 0 (CS0)
spi.max_speed_hz = 1350000

mode = 'v'

# read from MCP3008 channel (0-7)
def read_adc(channel):
    if channel < 0 or channel > 7:
       return -1
    adc = spi.xfer2([1, (8+channel) << 4, 0])
    data = ((adc[1] & 3) << 8) + adc[2]
    return data

def conv_to_voltage(data):
    return ((data) / 1024.0) # normalizes from 0 to 5V in

def input_thread():
    global mode
    while True:
        user_input = input().strip().lower()
        if user_input in ['t', 'c', 'v', 'a']:
            mode = user_input

def print_vals():
    global mode

    try:
        while True:
            print("\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n")

            raw_temp = read_adc(3)
            raw_current = read_adc(4)
            raw_voltage = read_adc(2)

            voltage_temp = conv_to_voltage(raw_temp)
            voltage_current = conv_to_voltage(raw_current)
            voltage_sensor = conv_to_voltage(raw_voltage)

            temp_c = 100.0 * ((voltage_temp * 5.0) - 0.75) + 25.0
            temp_f = (temp_c * 9.0 / 5.0) + 32.0 # celsius to fahrenheit

            current = ((voltage_current * 5.0 - 2.5) / 0.1375) - 1

            gain = 4.8
            battery_voltage = voltage_sensor * gain
            if mode == 't':
                print("Temp: {:.2f} F".format(temp_f))
            elif mode == 'c':
                print("Current: {:.2f} A".format(current))
            elif mode == 'v':
                print("Voltage: {:.2f} V".format(battery_voltage))

            time.sleep(1)

    except KeyboardInterrupt:
        spi.close()

if __name__ == "__main__":
    thread = threading.Thread(target=input_thread, daemon=True)
    thread.start()

    print_vals()
