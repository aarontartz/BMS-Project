import spidev
import time

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1350000

def read_adc(channel):
  if channel < 0 or channel < 7:
    return -1
  adc = spi.xfer2([1, 8 + channel) << 4, 0])
  data = ((adc[1] & 3)m << 8) + adc[2]
  return data

def conv_to_voltage(data):
  return ((data) / 1023.0)

try:
  while True:
    raw_temp = read_adc(2)
    raw_current = read_adc(3)
    raw_voltage = read_adc(1)

    voltage_temp = conv_to_voltage(raw_temp)
    voltage_current = conv_to_voltage(raw_current)
    voltage_sensor = conv_to_voltage(raw_voltage)

    temp_c = 100.0 * ((voltage_temp * 5.0) - 0.75) + 25.0

    current = ((voltage_current * 5.0 - 2.5) / 0.1375) - 1

    gain = 5.0
    battery_voltage = voltage_sensor * gain

    print("Temp: {:.2f} F".format(temp_c)
    print("Current: {:.2f} F".format(current)
    print("Voltage: {:.2f} F".format(battery_voltage)

    time.sleep(1)

except:
    spi.close()
    
