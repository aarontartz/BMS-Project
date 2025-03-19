import serial

ser = serial.Serial('/dev/modem', baudrate = 9600, timeout = 1)

while True:
    data = ser.readline()
    if data: print(data.decode('utf-8').strip())