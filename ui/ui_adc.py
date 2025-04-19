import sys
import time
import spidev
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel,
    QGroupBox, QFormLayout
)
from PyQt5.QtCore import QTimer
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

#real‐time SOC history plot
class BatteryCanvas(FigureCanvas):
    def __init__(self, parent=None, width=6, height=3, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super(BatteryCanvas, self).__init__(self.fig)

        #initial SOC history
        self.soc_history = [0]
        self.time_history = [0]
        self.max_points = 300
        self.capacity_kwh = 60  #for range calc if desired

        #plot line
        self.line, = self.axes.plot(self.time_history, self.soc_history, '-', linewidth=2)
        self.axes.set_xlim(0, self.max_points)
        self.axes.set_ylim(0, 100)
        self.axes.set_xlabel('Time (s)')
        self.axes.set_ylabel('SOC (%)')
        self.axes.set_title('Battery State of Charge')
        self.axes.grid(True)

        #SOC text
        self.soc_text = self.axes.text(
            0.02, 0.95,
            f"SOC: {self.soc_history[-1]:.1f}%",
            transform=self.axes.transAxes,
            fontsize=12
        )

        self.fig.tight_layout()

    def update_soc(self, soc, dt):
        #time axis: last time + dt
        new_t = self.time_history[-1] + dt
        self.time_history.append(new_t)
        self.soc_history.append(soc)

        #trim
        if len(self.soc_history) > self.max_points:
            self.soc_history = self.soc_history[-self.max_points:]
            self.time_history = self.time_history[-self.max_points:]

        #update data
        self.line.set_data(self.time_history, self.soc_history)
        self.axes.set_xlim(self.time_history[0], self.time_history[-1] * 1.05)
        self.soc_text.set_text(f"SOC: {soc:.1f}%")
        self.draw()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.init_spi()
        self.init_timer()

    def init_ui(self):
        self.setWindowTitle("Real‑time SOC & Sensor Monitor")
        self.setGeometry(100, 100, 800, 600)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        #soc plot
        self.battery_canvas = BatteryCanvas(width=6, height=3)
        layout.addWidget(self.battery_canvas)

        #adc readings
        adc_group = QGroupBox("Local ADC Readings")
        form = QFormLayout()
        self.voltage_label = QLabel("N/A")
        self.current_label = QLabel("N/A")
        self.temp_label    = QLabel("N/A")
        form.addRow("Battery Voltage (V):",   self.voltage_label)
        form.addRow("Load Current (A):",      self.current_label)
        form.addRow("Temp (°F):",             self.temp_label)
        adc_group.setLayout(form)
        layout.addWidget(adc_group)

    def init_spi(self):
        #MCP3008 setup
        self.spi = spidev.SpiDev()
        self.spi.open(0, 0)
        self.spi.max_speed_hz = 1_350_000

        #parameters for SOC mapping
        self.volt_min = 11.2 #pack voltage at 0% SOC
        self.volt_max = 14.6 #pack voltage at 100% SOC

    def init_timer(self):
        #update every second
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_readings)
        self.timer.start(1000)

    def read_adc_raw(self, ch):
        if ch < 0 or ch > 7:
            return 0
        resp = self.spi.xfer2([1, (8 + ch) << 4, 0])
        return ((resp[1] & 3) << 8) + resp[2]

    def update_readings(self):
        #temperature
        raw_t = self.read_adc_raw(3)
        v_t   = (raw_t / 1024.0) * 5.0
        temp_c = 100.0 * (v_t - 0.75) + 25.0
        temp_f = temp_c * 9.0/5.0 + 32.0
        self.temp_label.setText(f"{temp_f:.1f}")

        #current
        raw_i = self.read_adc_raw(4)
        v_i   = (raw_i / 1024.0) * 5.0
        current = ((v_i - 2.5) / 0.1375) - 1.0
        self.current_label.setText(f"{current:.2f}")

        #voltage
        raw_v = self.read_adc_raw(2)
        v_s   = (raw_v / 1024.0) * 5.0
        batt_v = v_s * (self.volt_max / 5.0)
        self.voltage_label.setText(f"{batt_v:.2f}")

        soc = (batt_v - self.volt_min) / (self.volt_max - self.volt_min) * 100.0
        soc = max(0.0, min(100.0, soc))
        self.battery_canvas.update_soc(soc, dt=1)

    def closeEvent(self, event):
        self.spi.close()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

