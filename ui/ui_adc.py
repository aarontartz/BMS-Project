import sys
import os
import time
import spidev
from collections import deque
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QLabel, QGroupBox, QFormLayout
)
from PyQt5.QtCore import QTimer
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

# simple sysfs GPIO helper
class SysfsGPIO:
    def __init__(self, pin):
        self.pin = str(pin)
        base = "/sys/class/gpio"
        # export if needed
        if not os.path.exists(f"{base}/gpio{self.pin}"):
            with open(f"{base}/export", "w") as f:
                f.write(self.pin)
        # set direction to out
        with open(f"{base}/gpio{self.pin}/direction", "w") as f:
            f.write("out")
        self._value_path = f"{base}/gpio{self.pin}/value"

    def on(self):
        with open(self._value_path, "w") as f:
            f.write("1")

    def off(self):
        with open(self._value_path, "w") as f:
            f.write("0")


# SOC plot canvas
class BatteryCanvas(FigureCanvas):
    def __init__(self):
        fig = Figure(figsize=(6, 3), dpi=100)
        self.axes = fig.add_subplot(111)
        super().__init__(fig)

        self.soc_history  = [0]
        self.time_history = [0]
        self.max_points   = 300

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
        t_new = self.time_history[-1] + dt
        self.time_history.append(t_new)
        self.soc_history.append(soc)
        if len(self.soc_history) > self.max_points:
            self.soc_history  = self.soc_history[-self.max_points:]
            self.time_history = self.time_history[-self.max_points:]
        self.line.set_data(self.time_history, self.soc_history)
        self.axes.set_xlim(self.time_history[0], self.time_history[-1]*1.05)
        self.soc_text.set_text(f'SOC: {soc:.1f}%')
        self.draw()


# main window
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('SOC & Sensor Monitor with Safety')
        self.setGeometry(50, 50, 800, 600)

        # layout
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # SOC plot
        self.canvas = BatteryCanvas()
        layout.addWidget(self.canvas)

        # readings + status
        box = QGroupBox('Local ADC Readings')
        form = QFormLayout()

        self.voltage_label  = QLabel('N/A')
        self.voltage_status = QLabel('N/A')
        form.addRow('Battery Voltage (V):', self.voltage_label)
        form.addRow('Voltage Status:',       self.voltage_status)

        self.current_label  = QLabel('N/A')
        self.current_status = QLabel('N/A')
        form.addRow('Load Current (A):',     self.current_label)
        form.addRow('Current Status:',       self.current_status)

        self.temp_label     = QLabel('N/A')
        self.temp_status    = QLabel('N/A')
        form.addRow('Temp (°F):',            self.temp_label)
        form.addRow('Temp Status:',          self.temp_status)

        box.setLayout(form)
        layout.addWidget(box)

        # SPI + ADC
        self.spi = spidev.SpiDev()
        self.spi.open(0, 0)
        self.spi.max_speed_hz = 1_350_000
        self.spi.mode = 0b00

        # LiFePO4 pack bounds
        self.volt_min = 11.2
        self.volt_max = 14.6

        # safety kill pin on GPIO26
        self.kill = SysfsGPIO(26)
        self.kill.on()

        # thresholds
        self.MAX_TEMP    = 60.0
        self.RED_TEMP    = 75.0
        self.MAX_CURRENT = 5.0
        self.RED_CURRENT = 7.0
        self.MAX_VOLTAGE = 4.2
        self.RED_VOLTAGE = 4.5

        # buffers for averaging
        size = 5
        self.buf_t = deque(maxlen=size)
        self.buf_i = deque(maxlen=size)
        self.buf_v = deque(maxlen=size)

        # periodic update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_readings)
        self.timer.start(1000)  # every second

    def read_raw(self, ch):
        if ch < 0 or ch > 7:
            return 0
        r = self.spi.xfer2([1, (8+ch) << 4, 0])
        return ((r[1] & 3) << 8) + r[2]

    def update_readings(self):
        # temperature from ch3
        r_t = self.read_raw(3)
        v_t = r_t / 1024.0 * 5.0
        t_c = 100.0*(v_t - 0.75) + 25.0
        t_f = t_c * 9/5 + 32
        self.temp_label.setText(f'{t_f:.1f}')

        # current from ch4
        r_i = self.read_raw(4)
        v_i = r_i / 1024.0 * 5.0
        i_a = (v_i - 2.5)/0.1375 - 1.0
        self.current_label.setText(f'{i_a:.2f}')

        # voltage from ch2 → 12 V FS
        r_v = self.read_raw(2)
        v_s = r_v / 1024.0 * 5.0
        b_v = v_s * (12.0/5.0)
        self.voltage_label.setText(f'{b_v:.2f}')

        # SOC
        soc = (b_v - self.volt_min)/(self.volt_max - self.volt_min)*100
        soc = max(0, min(100, soc))
        self.canvas.update_soc(soc, 1)

        # safety
        red = (t_c > self.RED_TEMP or
               i_a > self.RED_CURRENT or
               b_v > self.RED_VOLTAGE)
        self.buf_t.append(t_c)
        self.buf_i.append(i_a)
        self.buf_v.append(b_v)

        yellow = False
        if len(self.buf_t) == self.buf_t.maxlen:
            at = sum(self.buf_t)/len(self.buf_t)
            ai = sum(self.buf_i)/len(self.buf_i)
            av = sum(self.buf_v)/len(self.buf_v)
            yellow = (at > self.MAX_TEMP or
                      ai > self.MAX_CURRENT or
                      av > self.MAX_VOLTAGE)

        if red:
            self.kill.off()   # trip immediately
        else:
            self.kill.on()    # safe otherwise

        # update status labels
        def status(val, buf, max_l, red_l):
            if val > red_l:
                return 'RED', 'color:red;'
            if len(buf)==buf.maxlen and sum(buf)/len(buf)>max_l:
                return 'YELLOW', 'color:orange;'
            return 'GREEN', 'color:green;'

        st_t, col_t = status(t_c, self.buf_t, self.MAX_TEMP, self.RED_TEMP)
        st_i, col_i = status(i_a, self.buf_i, self.MAX_CURRENT, self.RED_CURRENT)
        st_v, col_v = status(b_v, self.buf_v, self.MAX_VOLTAGE, self.RED_VOLTAGE)

        self.temp_status.setText(st_t);    self.temp_status.setStyleSheet(col_t)
        self.current_status.setText(st_i); self.current_status.setStyleSheet(col_i)
        self.voltage_status.setText(st_v); self.voltage_status.setStyleSheet(col_v)

    def closeEvent(self, event):
        self.kill.off()
        event.accept()


if __name__=='__main__':
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
