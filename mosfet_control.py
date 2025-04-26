"""
#####################################
How this code works
#####################################

I mentioned my manager gave me some good advice for this project to make it more real world-applicable.


1) filter out noise
2) use red and yellow limits

1) Noise filtering is done by averaging the last 5 readings of each sensor. 
This is done using a deque


2.a) Yellow Limits are undesired but not damaging to the system. The killswitch is only 
triggered when the averageof the deque is above the MAX_<VALUE> 

2.b) Red Limits are damaging to the system. The killswitch is triggered 
immediately when the sensor reading. Even if the average is below the red limit, 
if the sensor reading is above the red limit, the killswitch is triggered since we are
determining the chance of the Red reading being due to noise is less important 
than the potential to damage the system/environment



--------------------------------------------------
FREQUENCY
--------------------------------------------------
Right now, the frequency at which the sensors are read is set to 1 second. 
This is done using the time.monotonic() function. time.monotic is better 
than time.sleep because it does not tie up CPU resources. Using time.sleep prevents 
the CPU from doing anything else.
"""




import RPi.GPIO as GPIO
import time
from collections import deque
from sensor_readings import read_all_sensors

# === GPIO SETUP ===
MOSFET_PIN = 17
GPIO.setmode(GPIO.BCM)
GPIO.setup(MOSFET_PIN, GPIO.OUT)
GPIO.output(MOSFET_PIN, GPIO.HIGH)

# === YELLOW LIMITS ===
MAX_TEMP = 60.0
MAX_CURRENT = 5.0
MAX_VOLTAGE = 4.2


# === RED LIMITS ===
RED_TEMP = 75.0
RED_CURRENT = 7.0
RED_VOLTAGE = 4.5

# === BUFFER SETUP ===
BUFFER_SIZE = 5
temp_buf = deque(maxlen=BUFFER_SIZE)
current_buf = deque(maxlen=BUFFER_SIZE)
voltage_buf = deque(maxlen=BUFFER_SIZE)

# === TIMING SETUP ===
INTERVAL = 1  # seconds
last_check_time = time.monotonic()

try:
    while True:
        now = time.monotonic()
        if now - last_check_time >= INTERVAL:
            last_check_time = now

            # === READ SENSORS ===
            temp_c, current, battery_voltage = read_all_sensors()

            # === RED LIMIT CHECK ===
            if temp_c > RED_TEMP or current > RED_CURRENT or battery_voltage > RED_VOLTAGE:
                print("RED LIMIT TRIGGERED! IMMEDIATE SHUTDOWN")
                GPIO.output(MOSFET_PIN, GPIO.LOW)
                break

            # === AVERAGING ===
            temp_buf.append(temp_c)
            current_buf.append(current)
            voltage_buf.append(battery_voltage)

            if len(temp_buf) == BUFFER_SIZE:
                avg_temp = sum(temp_buf) / BUFFER_SIZE
                avg_current = sum(current_buf) / BUFFER_SIZE
                avg_voltage = sum(voltage_buf) / BUFFER_SIZE

                print(f"[AVG] Temp: {avg_temp:.2f} C | Current: {avg_current:.2f} A | Voltage: {avg_voltage:.2f} V")

                if avg_temp > MAX_TEMP or avg_current > MAX_CURRENT or avg_voltage > MAX_VOLTAGE:
                    print("AVERAGE LIMIT EXCEEDED — SHUTTING DOWN")
                    GPIO.output(MOSFET_PIN, GPIO.LOW)
                else:
                    GPIO.output(MOSFET_PIN, GPIO.HIGH)
            else:
                print("Gathering initial readings...")

except KeyboardInterrupt:
    print("Exiting safely...")
    GPIO.output(MOSFET_PIN, GPIO.LOW)
    GPIO.cleanup()
