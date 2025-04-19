#!/usr/bin/env python3
import sys
import spidev
import gpiod
from collections import deque
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QLabel, QGroupBox, QFormLayout
)
from PyQt5.QtCore import QTimer
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

#GPIO setup: line 26 as output, default LOW
chip      = gpiod.Chip('gpiochip0')
kill_line = chip.get_line(26)
kill_line.request(
    consumer="battery_monitor",
    type=gpiod.LINE_REQ_DIR_OUT,
    default_vals=[0]
)

class BatteryCanvas(FigureCanvas):
    def __init__(self):
        fig = Figure(figsize=(6, 3), dpi=100)
        self.axes = fig.add_subplot(111)
        super().__init__(fig)

        self.soc_history = [0]
        self.time_history = [0]
        self.max_points = 300
        self.line, = self.axes.plot([], [], "-", linewidth=2)
        self.axes.set_xlim(0, self.max_points)
        self.axes.set_ylim(0, 100)
        self.axes.set_xlabel("Time (s)")
        self.axes.set_ylabel("SOC (%)")
        self.axes.set_title("Battery State of Charge")
        self.axes.grid(True)
        self.soc_text = self.axes.text(
            0.02, 0.95, "SOC: 0%", transform=self.axes.transAxes
        )
        fig.tight_layout()

    def update_soc(self, soc, dt):
        t_new = self.time_history[-1] + dt
        self.time_history.append(t_new)
        self.soc_history.append(soc)
        if len(self.soc_history) > self.max_points:
            self.soc_history = self.soc_history[-self.max_points:]
            self.time_history = self.time_history[-self.max_points:]
        self.line.set_data(self.time_history, self.soc_history)
        self.axes.set_xlim(
            self.time_history[0], self.time_history[-1] * 1.05
        )
        self.soc_text.set_text(f"SOC: {soc:.1f}%")
        self.draw()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SOC & Sensor Monitor with Safety")
        self.setGeometry(50, 50, 800, 600)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # SOC plot
        self.canvas = BatteryCanvas()
        layout.addWidget(self.canvas)

        # ADC readings + status
        box = QGroupBox("Local ADC Readings")
        form = QFormLayout()
        self.voltage_label  = QLabel("N/A"); self.voltage_status = QLabel("N/A")
        self.current_label  = QLabel("N/A"); self.current_status = QLabel("N/A")
        self.temp_label     = QLabel("N/A"); self.temp_status    = QLabel("N/A")
        form.addRow("Battery Voltage (V):", self.voltage_label)
        form.addRow("Voltage Status:",        self.voltage_status)
        form.addRow("Load Current (A):",      self.current_label)
        form.addRow("Current Status:",        self.current_status)
        form.addRow("Temp (°F):",             self.temp_label)
        form.addRow("Temp Status:",           self.temp_status)
        box.setLayout(form)
        layout.addWidget(box)

        # SPI/MCP3008 setup
        self.spi = spidev.SpiDev()
        self.spi.open(0, 0)
        self.spi.max_speed_hz = 1_350_000
        self.spi.mode = 0b00

        # battery pack bounds (11.2–14.6V)
        self.volt_min = 11.2  # UPDATE LATER IF NEEDED
        self.volt_max = 14.6  # UPDATE LATER IF NEEDED

        # safety thresholds
        self.MAX_TEMP    = 60.0;  self.RED_TEMP    = 75.0  # UPDATE LATER IF NEEDED
        self.MAX_CURRENT = 5.0;   self.RED_CURRENT = 7.0  # UPDATE LATER IF NEEDED
        self.MAX_VOLTAGE = 14.2;  self.RED_VOLTAGE = 14.6  # UPDATE LATER IF NEEDED

        # rolling buffers
        size = 5
        self.buf_t = deque(maxlen=size)
        self.buf_i = deque(maxlen=size)
        self.buf_v = deque(maxlen=size)

        # start periodic updates
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_readings)
        self.timer.start(1000)

    def read_raw(self, ch):
        if not (0 <= ch <= 7):
            return 0
        r = self.spi.xfer2([1, (8 + ch) << 4, 0])
        return ((r[1] & 3) << 8) + r[2]

    def update_readings(self):
        # --- read sensors ---
        r_t = self.read_raw(3)
        v_t = r_t / 1024.0 * 5.0
        t_c = 100*(v_t - 0.75) + 25
        t_f = t_c * 9/5 + 32
        self.temp_label.setText(f"{t_f:.1f}")

        r_i = self.read_raw(4)
        v_i = r_i / 1024.0 * 5.0
        i_a = (v_i - 2.5)/0.1375 - 1
        self.current_label.setText(f"{i_a:.2f}")

        r_v = self.read_raw(2)
        v_s = r_v / 1024.0 * 5.0
        b_v = v_s * (self.volt_max / 5.0)
        self.voltage_label.setText(f"{b_v:.2f}")

        # SOC
        soc = (b_v - self.volt_min)/(self.volt_max - self.volt_min)*100
        soc = max(0, min(100, soc))
        self.canvas.update_soc(soc, 1)

        # safety logic
        red = (t_c > self.RED_TEMP) or (i_a > self.RED_CURRENT) or (b_v > self.RED_VOLTAGE)
        self.buf_t.append(t_c); self.buf_i.append(i_a); self.buf_v.append(b_v)

        if len(self.buf_t) == self.buf_t.maxlen:
            at = sum(self.buf_t)/len(self.buf_t)
            ai = sum(self.buf_i)/len(self.buf_i)
            av = sum(self.buf_v)/len(self.buf_v)
            yellow = (at > self.MAX_TEMP) or (ai > self.MAX_CURRENT) or (av > self.MAX_VOLTAGE)
        else:
            yellow = False

        # drive kill‑switch: LOW (0 V) when safe, HIGH (3.3 V) when RED
        kill_line.set_value(int(red))

        # update status labels
        def status(val, buf, max_l, red_l):
            if val > red_l:
                return "RED", "color:red;"
            if len(buf)==buf.maxlen and sum(buf)/len(buf)>max_l:
                return "YELLOW", "color:orange;"
            return "GREEN", "color:green;"

        st_t, ct = status(t_c, self.buf_t, self.MAX_TEMP, self.RED_TEMP)
        st_i, ci = status(i_a, self.buf_i, self.MAX_CURRENT, self.RED_CURRENT)
        st_v, cv = status(b_v, self.buf_v, self.MAX_VOLTAGE, self.RED_VOLTAGE)

        self.temp_status.setText(st_t);    self.temp_status.setStyleSheet(ct)
        self.current_status.setText(st_i); self.current_status.setStyleSheet(ci)
        self.voltage_status.setText(st_v); self.voltage_status.setStyleSheet(cv)

    def closeEvent(self, event):
        # ensure kill‑switch goes LOW on exit
        kill_line.set_value(0)
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
