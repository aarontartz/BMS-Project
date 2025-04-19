import sys
import time
import spidev
from gpiozero import Device, DigitalOutputDevice
from gpiozero.pins.gpiod import PiGPIODFactory
from collections import deque
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QLabel, QGroupBox, QFormLayout
)
from PyQt5.QtCore import QTimer
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

# use libgpiod backend on Ubuntu
Device.pin_factory = PiGPIODFactory()

# SOC plot
class BatteryCanvas(FigureCanvas):
    def __init__(self, parent=None, width=6, height=3, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super().__init__(fig)
        self.soc_history = [0]
        self.time_history = [0]
        self.max_points = 300
        self.line, = self.axes.plot([], [], '-', linewidth=2)
        self.axes.set_xlim(0, self.max_points)
        self.axes.set_ylim(0, 100)
        self.axes.set_xlabel('Time (s)')
        self.axes.set_ylabel('SOC (%)')
        self.axes.set_title('Battery State of Charge')
        self.axes.grid(True)
        self.soc_text = self.axes.text(
            0.02, 0.95, 'SOC: 0.0%',
            transform=self.axes.transAxes, fontsize=12
        )
        fig.tight_layout()

    def update_soc(self, soc, dt):
        # update SOC history
        t_new = self.time_history[-1] + dt
        self.time_history.append(t_new)
        self.soc_history.append(soc)
        if len(self.soc_history) > self.max_points:
            self.soc_history = self.soc_history[-self.max_points:]
            self.time_history = self.time_history[-self.max_points:]
        self.line.set_data(self.time_history, self.soc_history)
        self.axes.set_xlim(self.time_history[0], self.time_history[-1] * 1.05)
        self.soc_text.set_text(f'SOC: {soc:.1f}%')
        self.draw()

# main window
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.init_spi()
        self.init_safety()
        self.init_timer()

    def init_ui(self):
        self.setWindowTitle('SOC & Sensor Monitor with Safety')
        self.setGeometry(50, 50, 800, 600)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # SOC canvas
        self.battery_canvas = BatteryCanvas(width=6, height=3)
        layout.addWidget(self.battery_canvas)

        # sensor readings
        readings = QGroupBox('Local ADC Readings')
        form = QFormLayout()
        self.voltage_label = QLabel('N/A')
        self.voltage_status = QLabel('N/A')
        form.addRow('Battery Voltage (V):', self.voltage_label)
        form.addRow('Voltage Status:', self.voltage_status)

        self.current_label = QLabel('N/A')
        self.current_status = QLabel('N/A')
        form.addRow('Load Current (A):', self.current_label)
        form.addRow('Current Status:', self.current_status)

        self.temp_label = QLabel('N/A')
        self.temp_status = QLabel('N/A')
        form.addRow('Temp (°F):', self.temp_label)
        form.addRow('Temp Status:', self.temp_status)

        readings.setLayout(form)
        layout.addWidget(readings)

    def init_spi(self):
        # SPI setup for MCP3008
        self.spi = spidev.SpiDev()
        self.spi.open(0, 0)
        self.spi.max_speed_hz = 1350000
        self.spi.mode = 0b00
        # LiFePO4 pack voltage bounds
        self.volt_min = 11.2
        self.volt_max = 14.6

    def init_safety(self):
        # kill switch on GPIO26
        self.kill = DigitalOutputDevice(26, active_high=True, initial_value=True)
        # limits
        self.MAX_TEMP = 60.0
        self.RED_TEMP = 75.0
        self.MAX_CURRENT = 5.0
        self.RED_CURRENT = 7.0
        self.MAX_VOLTAGE = 4.2
        self.RED_VOLTAGE = 4.5
        # buffers for averaging
        self.buf_size = 5
        self.temp_buf = deque(maxlen=self.buf_size)
        self.current_buf = deque(maxlen=self.buf_size)
        self.voltage_buf = deque(maxlen=self.buf_size)

    def init_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_readings)
        self.timer.start(1000)

    def read_adc_raw(self, ch):
        if not 0 <= ch <= 7:
            return 0
        r = self.spi.xfer2([1, (8 + ch) << 4, 0])
        return ((r[1] & 3) << 8) + r[2]

    def update_readings(self):
        # read sensors
        raw_t = self.read_adc_raw(3)
        v_t = raw_t / 1024.0 * 5.0
        temp_c = 100.0 * (v_t - 0.75) + 25.0
        temp_f = temp_c * 9/5 + 32
        self.temp_label.setText(f"{temp_f:.1f}")

        raw_i = self.read_adc_raw(4)
        v_i = raw_i / 1024.0 * 5.0
        current = (v_i - 2.5) / 0.1375 - 1.0
        self.current_label.setText(f"{current:.2f}")

        raw_v = self.read_adc_raw(2)
        v_s = raw_v / 1024.0 * 5.0
        batt_v = v_s * (12.0 / 5.0)
        self.voltage_label.setText(f"{batt_v:.2f}")

        # update SOC
        soc = (batt_v - self.volt_min) / (self.volt_max - self.volt_min) * 100
        soc = max(0, min(100, soc))
        self.battery_canvas.update_soc(soc, dt=1)

        # safety logic
        red_trip = (
            temp_c > self.RED_TEMP or
            current > self.RED_CURRENT or
            batt_v > self.RED_VOLTAGE
        )
        self.temp_buf.append(temp_c)
        self.current_buf.append(current)
        self.voltage_buf.append(batt_v)
        yellow_trip = False
        if len(self.temp_buf) == self.buf_size:
            avg_t = sum(self.temp_buf) / self.buf_size
            avg_i = sum(self.current_buf) / self.buf_size
            avg_v = sum(self.voltage_buf) / self.buf_size
            yellow_trip = (
                avg_t > self.MAX_TEMP or
                avg_i > self.MAX_CURRENT or
                avg_v > self.MAX_VOLTAGE
            )
        if red_trip:
            self.kill.off()
        else:
            self.kill.on()

        # update status colors
        def status(raw, buf, max_l, red_l):
            if raw > red_l:
                return 'RED', 'color:red;'
            if len(buf) == self.buf_size and sum(buf) / len(buf) > max_l:
                return 'YELLOW', 'color:orange;'
            return 'GREEN', 'color:green;'

        s_t, c_t = status(temp_c, self.temp_buf, self.MAX_TEMP, self.RED_TEMP)
        s_i, c_i = status(current, self.current_buf, self.MAX_CURRENT, self.RED_CURRENT)
        s_v, c_v = status(batt_v, self.voltage_buf, self.MAX_VOLTAGE, self.RED_VOLTAGE)
        self.temp_status.setText(s_t)
        self.temp_status.setStyleSheet(c_t)
        self.current_status.setText(s_i)
        self.current_status.setStyleSheet(c_i)
        self.voltage_status.setText(s_v)
        self.voltage_status.setStyleSheet(c_v)

    def closeEvent(self, event):
        self.kill.off()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
