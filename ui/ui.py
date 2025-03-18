import sys
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.animation import FuncAnimation
import matplotlib.patches as patches
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QLabel, QSlider, QPushButton, 
                           QGroupBox, QFormLayout, QSpinBox, QDoubleSpinBox,
                           QComboBox, QTabWidget, QCheckBox, QRadioButton,
                           QButtonGroup, QToolTip, QMessageBox)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap, QIcon
import json
import random
import socket
import threading
import time
import requests
from datetime import datetime


class RemoteSensor:
    """class to simulate connection to remote energy monitoring sensors"""
    def __init__(self, sensor_id, sensor_type, location):
        self.sensor_id = sensor_id
        self.sensor_type = sensor_type  # sensor type
        self.location = location
        self.is_connected = False
        self.last_reading = None
        self.last_reading_time = None
        self.connection_thread = None
        self.stop_thread = False
        
    def connect(self):
        """simulate connecting to a remote sensor"""
        if not self.is_connected:
            self.is_connected = True
            self.stop_thread = False
            self.connection_thread = threading.Thread(target=self._reading_loop)
            self.connection_thread.daemon = True
            self.connection_thread.start()
            return True
        return False
        
    def disconnect(self):
        """disconnect from the remote sensor"""
        if self.is_connected:
            self.stop_thread = True
            self.is_connected = False
            if self.connection_thread:
                self.connection_thread.join(timeout=1.0)
            return True
        return False
        
    def _reading_loop(self):
        """simulate periodic sensor readings"""
        while not self.stop_thread:
            try:
                self._fetch_sensor_data()
                time.sleep(1)
            except Exception as e:
                print(f"error reading from sensor {self.sensor_id}: {e}")
                self.is_connected = False
                break
                
    def _fetch_sensor_data(self):
        """simulate fetching data from a remote sensor"""
        if self.sensor_type == "voltage":
            base_value = 400 if self.location == "grid" else 350
            noise = random.uniform(-5, 5)
            reading = base_value + noise
            unit = "V"
        elif self.sensor_type == "current":
            base_value = 30 if self.location == "grid" else 25
            noise = random.uniform(-2, 2)
            reading = base_value + noise
            unit = "A"
        elif self.sensor_type == "power":
            base_value = 11 if self.location == "grid" else 10
            noise = random.uniform(-0.5, 0.5)
            reading = base_value + noise
            unit = "kW"
        elif self.sensor_type == "temperature":
            base_value = 25 if self.location == "grid" else 35
            noise = random.uniform(-1, 1)
            reading = base_value + noise
            unit = "°C"
        else:
            reading = random.uniform(0, 100)
            unit = "units"
            
        self.last_reading = reading
        self.last_reading_time = datetime.now()
        self.last_reading_unit = unit
        
    def get_reading(self):
        """get the most recent sensor reading"""
        if self.is_connected and self.last_reading is not None:
            age = (datetime.now() - self.last_reading_time).total_seconds()
            return {
                "sensor_id": self.sensor_id,
                "type": self.sensor_type,
                "location": self.location,
                "value": self.last_reading,
                "unit": self.last_reading_unit,
                "timestamp": self.last_reading_time.isoformat(),
                "age_seconds": age
            }
        return None


class RemoteSensorManager:
    """manager for remote energy monitoring sensors"""
    def __init__(self):
        self.sensors = {}
        self.api_endpoint = "https://example.com/api/energy"
        
    def add_sensor(self, sensor_id, sensor_type, location):
        """add a sensor to the manager"""
        if sensor_id not in self.sensors:
            self.sensors[sensor_id] = RemoteSensor(sensor_id, sensor_type, location)
            return True
        return False
        
    def remove_sensor(self, sensor_id):
        """remove a sensor from the manager"""
        if sensor_id in self.sensors:
            if self.sensors[sensor_id].is_connected:
                self.sensors[sensor_id].disconnect()
            del self.sensors[sensor_id]
            return True
        return False
        
    def connect_all(self):
        """connect to all sensors"""
        for sensor in self.sensors.values():
            sensor.connect()
            
    def disconnect_all(self):
        """disconnect from all sensors"""
        for sensor in self.sensors.values():
            sensor.disconnect()
            
    def get_all_readings(self):
        """get readings from all sensors"""
        readings = {}
        for sensor_id, sensor in self.sensors.items():
            readings[sensor_id] = sensor.get_reading()
        return readings
        
    def check_grid_status(self):
        """simulate checking grid status via api"""
        try:
            grid_status = {
                "status": random.choice(["stable", "stable", "stable", "unstable", "peak"]),
                "current_demand": random.uniform(70, 95),
                "capacity": 100,
                "v2g_rate": random.uniform(0.18, 0.22),
                "timestamp": datetime.now().isoformat()
            }
            return grid_status
        except Exception as e:
            print(f"error fetching grid status: {e}")
            return None


class PowerFlowCanvas(FigureCanvas):
    """canvas for showing power flow between car and grid"""
    def __init__(self, parent=None, width=4, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        self.fig.patch.set_facecolor('#F0F0F0')
        
        super(PowerFlowCanvas, self).__init__(self.fig)
        
        # init components
        self.power_direction = 0
        self.power_value = 0
        
        self.setup_diagram()
        self.fig.tight_layout(pad=0)
        
    def setup_diagram(self):
        """set up the initial power flow diagram"""
        self.axes.clear()
        self.axes.set_xlim(0, 10)
        self.axes.set_ylim(0, 10)
        self.axes.axis('off')
        
        self.grid = patches.Rectangle((1, 5), 2, 3, fill=True, color='lightgray', alpha=0.5)
        self.house_roof = patches.Polygon([[1, 8], [2, 9], [3, 8]], fill=True, color='lightgray', alpha=0.7)
        
        self.car_body = patches.Rectangle((7, 5), 2, 1.5, fill=True, color='lightblue', alpha=0.7)
        self.car_top = patches.Rectangle((7.5, 6.5), 1, 0.8, fill=True, color='lightblue', alpha=0.7)
        self.wheel1 = patches.Circle((7.3, 5), 0.3, fill=True, color='black', alpha=0.7)
        self.wheel2 = patches.Circle((8.7, 5), 0.3, fill=True, color='black', alpha=0.7)
        
        self.power_line = patches.Rectangle((3, 6), 4, 0.3, fill=True, color='black', alpha=0.5)
        
        self.axes.add_patch(self.grid)
        self.axes.add_patch(self.house_roof)
        self.axes.add_patch(self.car_body)
        self.axes.add_patch(self.car_top)
        self.axes.add_patch(self.wheel1)
        self.axes.add_patch(self.wheel2)
        self.axes.add_patch(self.power_line)
        
        self.power_arrows = []
        
        self.grid_label = self.axes.text(2, 4, "Grid", ha='center', fontsize=10)
        self.car_label = self.axes.text(8, 4, "EV", ha='center', fontsize=10)
        self.power_text = self.axes.text(5, 7.5, "0 kW", ha='center', fontsize=12, fontweight='bold')
        self.direction_text = self.axes.text(5, 3, "Idle", ha='center', fontsize=12)
        
        self.draw()
        
    def update_power_flow(self, direction, power_kw):
        """update the power flow visualization"""
        self.power_direction = direction
        self.power_value = abs(power_kw)
        
        for arrow in self.power_arrows:
            arrow.remove()
        self.power_arrows = []
        
        self.power_text.set_text(f"{self.power_value:.1f} kW")
        
        if direction == 0:
            self.direction_text.set_text("Idle")
            self.power_text.set_color('black')
        elif direction > 0:
            self.direction_text.set_text("grid → vehicle (g2v)")
            self.power_text.set_color('green')
            num_arrows = min(int(self.power_value / 2) + 1, 5)
            for i in range(num_arrows):
                x_pos = 3 + i * (4 / max(num_arrows, 1))
                arrow = patches.Arrow(x_pos, 6.15, 0.5, 0, width=0.2, 
                                     color='green', alpha=0.8)
                self.axes.add_patch(arrow)
                self.power_arrows.append(arrow)
                
        else:
            self.direction_text.set_text("vehicle → grid (v2g)")
            self.power_text.set_color('blue')
            num_arrows = min(int(self.power_value / 2) + 1, 5)
            for i in range(num_arrows):
                x_pos = 7 - i * (4 / max(num_arrows, 1))
                arrow = patches.Arrow(x_pos, 6.15, -0.5, 0, width=0.2, 
                                     color='blue', alpha=0.8)
                self.axes.add_patch(arrow)
                self.power_arrows.append(arrow)
        
        self.draw()


class BatteryCanvas(FigureCanvas):
    """canvas for showing battery soc and history"""
    def __init__(self, parent=None, width=7, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        
        super(BatteryCanvas, self).__init__(self.fig)
        
        self.soc_history = [80]
        self.time_history = [0]
        self.max_history_points = 500
        self.battery_capacity = 60
        
        self.soc_line, = self.axes.plot(self.time_history, self.soc_history, 'b-', linewidth=2)
        self.axes.set_xlim(0, 60)
        self.axes.set_ylim(0, 100)
        self.axes.set_xlabel('Time (minutes)')
        self.axes.set_ylabel('State of Charge (%)')
        self.axes.set_title('Battery SOC History')
        self.axes.grid(True)
        
        self.soc_text = self.axes.text(0.02, 0.95, f"Current SOC: {self.soc_history[-1]:.1f}%", 
                                      transform=self.axes.transAxes, fontsize=12)
        self.range_text = self.axes.text(0.02, 0.90, f"Est. Range: {self.estimate_range(self.soc_history[-1]):.0f} km", 
                                      transform=self.axes.transAxes, fontsize=12)
        self.capacity_text = self.axes.text(0.02, 0.85, f"Capacity: {self.battery_capacity} kWh", 
                                         transform=self.axes.transAxes, fontsize=12)
        
        self.fig.tight_layout()
        
    def update_capacity(self, capacity):
        """update the battery capacity"""
        self.battery_capacity = capacity
        self.capacity_text.set_text(f"Capacity: {self.battery_capacity} kWh")
        self.range_text.set_text(f"Est. Range: {self.estimate_range(self.soc_history[-1]):.0f} km")
        self.draw()
        
    def estimate_range(self, soc):
        """estimate driving range based on soc and battery capacity"""
        km_per_kwh = 6
        available_energy = self.battery_capacity * (soc / 100)
        return available_energy * km_per_kwh
        
    def update_soc(self, new_soc, time_delta):
        """update the soc history with a new value"""
        self.soc_history.append(new_soc)
        new_time = self.time_history[-1] + time_delta
        self.time_history.append(new_time)
        
        if len(self.soc_history) > self.max_history_points:
            self.soc_history = self.soc_history[-self.max_history_points:]
            self.time_history = self.time_history[-self.max_history_points:]
        
        self.soc_line.set_data(self.time_history, self.soc_history)
        
        if new_time > self.axes.get_xlim()[1]:
            self.axes.set_xlim(0, new_time * 1.1)
            
        self.soc_text.set_text(f"Current SOC: {new_soc:.1f}%")
        self.range_text.set_text(f"Est. Range: {self.estimate_range(new_soc):.0f} km")
        self.draw()


class V2GSimulator(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.init_ui()
        
        # simulation params
        self.battery_capacity = 60
        self.current_soc = 80.0
        self.power = 0.0
        self.elapsed_time = 0
        self.time_step = 1/60
        self.v2g_enabled = True
        self.power_limit = 11
        self.charging_efficiency = 0.92
        self.discharging_efficiency = 0.90
        
        self.sim_timer = QTimer()
        self.sim_timer.timeout.connect(self.update_simulation)
        self.sim_timer.start(1000)
        
        self.battery_canvas.update_soc(self.current_soc, 0)
        self.update_ui_controls()
        
        self.power_flow_canvas.update_power_flow(0, 0)
        
    def init_ui(self):
        """initialize the ui components"""
        self.setWindowTitle('V2G Battery Simulator with Remote Sensors')
        self.setGeometry(100, 100, 1200, 800)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        title_label = QLabel("Electric Vehicle Battery V2G Simulator")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        self.tabs = QTabWidget()
        
        main_tab = QWidget()
        main_layout_tab = QHBoxLayout(main_tab)
        
        viz_layout = QVBoxLayout()
        
        self.battery_canvas = BatteryCanvas(width=6, height=4)
        viz_layout.addWidget(self.battery_canvas)
        
        self.power_flow_canvas = PowerFlowCanvas(width=6, height=3)
        viz_layout.addWidget(self.power_flow_canvas)
        
        main_layout_tab.addLayout(viz_layout, 7)
        
        controls_widget = QWidget()
        controls_layout = QVBoxLayout(controls_widget)
        
        battery_group = QGroupBox("Battery Properties")
        battery_layout = QFormLayout()
        
        self.capacity_spinner = QSpinBox()
        self.capacity_spinner.setRange(20, 200)
        self.capacity_spinner.setValue(60)
        self.capacity_spinner.setSuffix(" kWh")
        self.capacity_spinner.valueChanged.connect(self.update_battery_capacity)
        battery_layout.addRow("Battery Capacity:", self.capacity_spinner)
        
        self.soc_spinner = QDoubleSpinBox()
        self.soc_spinner.setRange(0, 100)
        self.soc_spinner.setValue(80)
        self.soc_spinner.setSuffix(" %")
        self.soc_spinner.valueChanged.connect(self.manual_soc_update)
        battery_layout.addRow("Set SOC:", self.soc_spinner)
        
        battery_group.setLayout(battery_layout)
        controls_layout.addWidget(battery_group)
        
        power_group = QGroupBox("Power Control")
        power_layout = QVBoxLayout()
        
        mode_layout = QHBoxLayout()
        self.mode_group = QButtonGroup(self)
        
        self.idle_radio = QRadioButton("Idle")
        self.idle_radio.setChecked(True)
        self.mode_group.addButton(self.idle_radio, 0)
        
        self.charging_radio = QRadioButton("Charging (G2V)")
        self.mode_group.addButton(self.charging_radio, 1)
        
        self.v2g_radio = QRadioButton("V2G")
        self.mode_group.addButton(self.v2g_radio, 2)
        
        mode_layout.addWidget(self.idle_radio)
        mode_layout.addWidget(self.charging_radio)
        mode_layout.addWidget(self.v2g_radio)
        
        self.mode_group.buttonClicked.connect(self.power_mode_changed)
        power_layout.addLayout(mode_layout)
        
        slider_layout = QFormLayout()
        self.power_slider = QSlider(Qt.Horizontal)
        self.power_slider.setRange(0, 100)
        self.power_slider.setValue(0)
        self.power_slider.valueChanged.connect(self.update_power)
        
        self.power_label = QLabel("0.0 kW")
        slider_layout.addRow("Power Level:", self.power_slider)
        slider_layout.addRow("Current Power:", self.power_label)
        
        self.max_power_spinner = QDoubleSpinBox()
        self.max_power_spinner.setRange(1, 350)
        self.max_power_spinner.setValue(11)
        self.max_power_spinner.setSuffix(" kW")
        self.max_power_spinner.valueChanged.connect(self.update_power_limit)
        slider_layout.addRow("Max Power:", self.max_power_spinner)
        
        power_layout.addLayout(slider_layout)
        
        efficiency_layout = QFormLayout()
        
        self.charging_eff_spinner = QDoubleSpinBox()
        self.charging_eff_spinner.setRange(50, 100)
        self.charging_eff_spinner.setValue(92)
        self.charging_eff_spinner.setSuffix(" %")
        self.charging_eff_spinner.valueChanged.connect(self.update_efficiency)
        efficiency_layout.addRow("Charging Efficiency:", self.charging_eff_spinner)
        
        self.discharging_eff_spinner = QDoubleSpinBox()
        self.discharging_eff_spinner.setRange(50, 100)
        self.discharging_eff_spinner.setValue(90)
        self.discharging_eff_spinner.setSuffix(" %")
        self.discharging_eff_spinner.valueChanged.connect(self.update_efficiency)
        efficiency_layout.addRow("V2G Efficiency:", self.discharging_eff_spinner)
        
        power_layout.addLayout(efficiency_layout)
        
        power_group.setLayout(power_layout)
        controls_layout.addWidget(power_group)
        
        sim_group = QGroupBox("Simulation Control")
        sim_layout = QHBoxLayout()
        
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["Real-time", "2x Speed", "5x Speed", "10x Speed"])
        self.speed_combo.currentIndexChanged.connect(self.change_sim_speed)
        
        self.pause_button = QPushButton("Pause")
        self.pause_button.setCheckable(True)
        self.pause_button.clicked.connect(self.toggle_simulation)
        
        self.reset_button = QPushButton("Reset")
        self.reset_button.clicked.connect(self.reset_simulation)
        
        sim_layout.addWidget(QLabel("Simulation Speed:"))
        sim_layout.addWidget(self.speed_combo)
        sim_layout.addWidget(self.pause_button)
        sim_layout.addWidget(self.reset_button)
        
        sim_group.setLayout(sim_layout)
        controls_layout.addWidget(sim_group)
        
        stats_group = QGroupBox("Battery Statistics")
        stats_layout = QVBoxLayout()
        
        self.stats_label = QLabel()
        self.stats_label.setFont(QFont("Monospace", 10))
        stats_layout.addWidget(self.stats_label)
        
        stats_group.setLayout(stats_layout)
        controls_layout.addWidget(stats_group)
        
        controls_layout.addStretch(1)
        
        main_layout_tab.addWidget(controls_widget, 3)
        
        self.tabs.addTab(main_tab, "Main")
        
        main_layout.addWidget(self.tabs)
        
        self.statusBar().showMessage("ready. simulation running in real-time.")
        
        self.init_sensor_manager()
        self.init_sensor_ui()
        
    def init_sensor_manager(self):
        """initialize the sensor manager and add sensors"""
        self.sensor_manager = RemoteSensorManager()
        self.sensor_manager.add_sensor("grid_voltage", "voltage", "grid")
        self.sensor_manager.add_sensor("grid_current", "current", "grid")
        self.sensor_manager.add_sensor("grid_power", "power", "grid")
        self.sensor_manager.add_sensor("car_voltage", "voltage", "vehicle")
        self.sensor_manager.add_sensor("car_current", "current", "vehicle")
        self.sensor_manager.add_sensor("car_power", "power", "vehicle")
        self.sensor_manager.add_sensor("battery_temp", "temperature", "vehicle")
        
        self.sensor_timer = QTimer()
        self.sensor_timer.timeout.connect(self.update_sensor_readings)
        
        self.sensors_connected = False
        
    def init_sensor_ui(self):
        """initialize ui components for remote sensors"""
        self.sensor_tab = QWidget()
        sensor_layout = QVBoxLayout(self.sensor_tab)
        
        connection_group = QGroupBox("Remote Sensor Connection")
        connection_layout = QVBoxLayout()
        
        connection_form = QFormLayout()
        self.sensor_status_label = QLabel("Not connected")
        self.sensor_status_label.setStyleSheet("color: red;")
        connection_form.addRow("Sensor Status:", self.sensor_status_label)
        
        self.connect_button = QPushButton("Connect to Sensors")
        self.connect_button.clicked.connect(self.connect_to_sensors)
        
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self.disconnect_from_sensors)
        self.disconnect_button.setEnabled(False)
        
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.connect_button)
        button_layout.addWidget(self.disconnect_button)
        
        connection_layout.addLayout(connection_form)
        connection_layout.addLayout(button_layout)
        connection_group.setLayout(connection_layout)
        sensor_layout.addWidget(connection_group)
        
        readings_group = QGroupBox("Current Sensor Readings")
        readings_layout = QVBoxLayout()
        readings_grid = QFormLayout()
        
        self.sensor_labels = {}
        for sensor_id in self.sensor_manager.sensors:
            sensor = self.sensor_manager.sensors[sensor_id]
            label = QLabel("N/A")
            self.sensor_labels[sensor_id] = label
            readings_grid.addRow(f"{sensor.location.capitalize()} {sensor.sensor_type.capitalize()}:", label)
        
        readings_layout.addLayout(readings_grid)
        readings_group.setLayout(readings_layout)
        sensor_layout.addWidget(readings_group)
        
        grid_group = QGroupBox("Grid Status (API)")
        grid_layout = QFormLayout()
        
        self.grid_status_label = QLabel("Unknown")
        grid_layout.addRow("Status:", self.grid_status_label)
        
        self.grid_demand_label = QLabel("N/A")
        grid_layout.addRow("Current Demand:", self.grid_demand_label)
        
        self.grid_v2g_rate_label = QLabel("N/A")
        grid_layout.addRow("V2G Rate:", self.grid_v2g_rate_label)
        
        grid_group.setLayout(grid_layout)
        sensor_layout.addWidget(grid_group)
        
        sensor_layout.addStretch(1)
        
        self.tabs.addTab(self.sensor_tab, "Remote Sensors")
        
    def connect_to_sensors(self):
        """connect to all remote sensors"""
        try:
            self.statusBar().showMessage("connecting to remote sensors...")
            self.sensor_manager.connect_all()
            self.sensor_status_label.setText("Connected")
            self.sensor_status_label.setStyleSheet("color: green; font-weight: bold;")
            self.connect_button.setEnabled(False)
            self.disconnect_button.setEnabled(True)
            self.sensor_timer.start(1000)
            self.sensors_connected = True
            self.statusBar().showMessage("connected to remote sensors")
        except Exception as e:
            self.statusBar().showMessage(f"error connecting to sensors: {str(e)}")
            QMessageBox.critical(self, "Connection Error", 
                              f"failed to connect to remote sensors: {str(e)}")

    def disconnect_from_sensors(self):
        """disconnect from all remote sensors"""
        try:
            self.statusBar().showMessage("disconnecting from remote sensors...")
            self.sensor_manager.disconnect_all()
            self.sensor_timer.stop()
            self.sensor_status_label.setText("Disconnected")
            self.sensor_status_label.setStyleSheet("color: red;")
            self.connect_button.setEnabled(True)
            self.disconnect_button.setEnabled(False)
            for sensor_id, label in self.sensor_labels.items():
                label.setText("N/A")
            
            self.grid_status_label.setText("Unknown")
            self.grid_demand_label.setText("N/A")
            self.grid_v2g_rate_label.setText("N/A")
            
            self.sensors_connected = False
            self.statusBar().showMessage("disconnected from remote sensors")
        except Exception as e:
            self.statusBar().showMessage(f"error disconnecting from sensors: {str(e)}")

    def update_sensor_readings(self):
        """update the displayed sensor readings"""
        try:
            readings = self.sensor_manager.get_all_readings()
            for sensor_id, reading in readings.items():
                if reading:
                    label = self.sensor_labels.get(sensor_id)
                    if label:
                        value = reading["value"]
                        unit = reading["unit"]
                        label.setText(f"{value:.2f} {unit}")
            
            current_time = time.time()
            if not hasattr(self, 'last_grid_check') or current_time - self.last_grid_check > 5:
                self.last_grid_check = current_time
                self.update_grid_status()
                
            self.integrate_sensor_data(readings)
                
        except Exception as e:
            print(f"error updating sensor readings: {e}")

    def update_grid_status(self):
        """update the grid status display"""
        try:
            grid_status = self.sensor_manager.check_grid_status()
            if grid_status:
                status = grid_status["status"]
                if status == "stable":
                    self.grid_status_label.setText("Stable")
                    self.grid_status_label.setStyleSheet("color: green;")
                elif status == "unstable":
                    self.grid_status_label.setText("Unstable")
                    self.grid_status_label.setStyleSheet("color: orange;")
                elif status == "peak":
                    self.grid_status_label.setText("Peak Demand")
                    self.grid_status_label.setStyleSheet("color: red;")
                
                demand = grid_status["current_demand"]
                capacity = grid_status["capacity"]
                self.grid_demand_label.setText(f"{demand:.1f}% of capacity")
                
                v2g_rate = grid_status["v2g_rate"]
                self.grid_v2g_rate_label.setText(f"${v2g_rate:.2f}/kWh")
                
                if status == "peak" and self.current_soc > 40 and not self.v2g_radio.isChecked():
                    self.statusBar().showMessage("peak demand detected! v2g opportunity available.")
        except Exception as e:
            print(f"error updating grid status: {e}")

    def integrate_sensor_data(self, readings):
        """use sensor data to inform the simulation"""
        try:
            if ('car_power' in readings and readings['car_power'] and 
                'grid_power' in readings and readings['grid_power']):
                
                car_power = readings['car_power']['value']
                grid_power = readings['grid_power']['value']
                
                if self.power > 0.1:
                    measured_efficiency = (car_power / grid_power) if grid_power > 0 else 0
                    if 0.7 < measured_efficiency < 0.99 and abs(measured_efficiency - self.charging_efficiency) > 0.02:
                        self.charging_efficiency = 0.9 * self.charging_efficiency + 0.1 * measured_efficiency
                        self.charging_eff_spinner.setValue(self.charging_efficiency * 100)
                        
                elif self.power < -0.1:
                    measured_efficiency = (grid_power / car_power) if car_power > 0 else 0
                    if 0.7 < measured_efficiency < 0.99 and abs(measured_efficiency - self.discharging_efficiency) > 0.02:
                        self.discharging_efficiency = 0.9 * self.discharging_efficiency + 0.1 * measured_efficiency
                        self.discharging_eff_spinner.setValue(self.discharging_efficiency * 100)
                        
            if 'battery_temp' in readings and readings['battery_temp']:
                battery_temp = readings['battery_temp']['value']
                if battery_temp > 40:
                    temp_factor = 1.0 - (battery_temp - 40) * 0.01
                    temp_factor = max(0.8, temp_factor)
                    self.charging_efficiency = self.charging_efficiency * 0.9 + 0.1 * (self.charging_efficiency * temp_factor)
                    self.discharging_efficiency = self.discharging_efficiency * 0.9 + 0.1 * (self.discharging_efficiency * temp_factor)
                    self.charging_eff_spinner.setValue(self.charging_efficiency * 100)
                    self.discharging_eff_spinner.setValue(self.discharging_efficiency * 100)
                    if temp_factor < 0.95:
                        self.statusBar().showMessage(f"warning: high battery temperature ({battery_temp:.1f}°c) reducing efficiency")
                    
        except Exception as e:
            print(f"error integrating sensor data: {e}")
        
    def update_ui_controls(self):
        """update ui controls to match simulation state"""
        self.soc_spinner.setValue(self.current_soc)
        self.capacity_spinner.setValue(self.battery_capacity)
        
        if abs(self.power) < 0.1:
            self.idle_radio.setChecked(True)
        elif self.power > 0:
            self.charging_radio.setChecked(True)
        else:
            self.v2g_radio.setChecked(True)
        
        power_pct = int(abs(self.power) / self.power_limit * 100)
        self.power_slider.setValue(power_pct)
        self.power_label.setText(f"{abs(self.power):.1f} kW")
        self.charging_eff_spinner.setValue(self.charging_efficiency * 100)
        self.discharging_eff_spinner.setValue(self.discharging_efficiency * 100)
        self.update_stats()
        
    def update_stats(self):
        """update the statistics display"""
        energy_available = self.battery_capacity * (self.current_soc / 100)
        range_km = self.battery_canvas.estimate_range(self.current_soc)
        
        max_charge_time = 0
        if self.power > 0.1:
            remaining_capacity = self.battery_capacity * (1 - self.current_soc / 100)
            max_charge_time = remaining_capacity / (self.power * self.charging_efficiency) * 60
        
        max_discharge_time = 0
        if self.power < -0.1:
            max_discharge_time = energy_available / (abs(self.power) / self.discharging_efficiency) * 60
        
        stats_text = (
            f"Available Energy: {energy_available:.1f} kWh\n"
            f"Estimated Range: {range_km:.1f} km\n"
            f"Elapsed Time: {self.elapsed_time:.1f} minutes\n"
        )
        
        if self.power > 0.1:
            stats_text += f"Time to Full: {max_charge_time:.1f} minutes\n"
        elif self.power < -0.1:
            stats_text += f"Time to Empty: {max_discharge_time:.1f} minutes\n"
            
        if self.power != 0:
            kwh_per_minute = abs(self.power) / 60
            energy_transferred = kwh_per_minute * self.elapsed_time
            
            if self.power > 0:
                stats_text += f"Energy Charged: {energy_transferred:.2f} kWh\n"
                cost = energy_transferred * 0.15
                stats_text += f"Cost: ${cost:.2f}\n"
            else:
                stats_text += f"Energy Exported: {energy_transferred:.2f} kWh\n"
                revenue = energy_transferred * 0.20
                stats_text += f"Revenue: ${revenue:.2f}\n"
        
        self.stats_label.setText(stats_text)
    
    def power_mode_changed(self, button):
        """handle power mode radio button changes"""
        mode = self.mode_group.id(button)
        if mode == 0:
            self.power = 0
            self.power_slider.setValue(0)
            self.power_flow_canvas.update_power_flow(0, 0)
        elif mode == 1:
            power_pct = self.power_slider.value()
            self.power = (power_pct / 100) * self.power_limit
            self.power_flow_canvas.update_power_flow(1, self.power)
        else:
            power_pct = self.power_slider.value()
            self.power = -(power_pct / 100) * self.power_limit
            self.power_flow_canvas.update_power_flow(-1, abs(self.power))
        self.power_label.setText(f"{abs(self.power):.1f} kW")
    
    def update_power(self):
        """update power based on slider value"""
        power_pct = self.power_slider.value()
        if self.idle_radio.isChecked():
            self.power = 0
            self.power_flow_canvas.update_power_flow(0, 0)
        elif self.charging_radio.isChecked():
            self.power = (power_pct / 100) * self.power_limit
            self.power_flow_canvas.update_power_flow(1, self.power)
        else:
            self.power = -(power_pct / 100) * self.power_limit
            self.power_flow_canvas.update_power_flow(-1, abs(self.power))
        self.power_label.setText(f"{abs(self.power):.1f} kW")
    
    def update_power_limit(self, value):
        """update the maximum power limit"""
        self.power_limit = value
        power_pct = self.power_slider.value()
        if self.charging_radio.isChecked():
            self.power = (power_pct / 100) * self.power_limit
            self.power_flow_canvas.update_power_flow(1, self.power)
        elif self.v2g_radio.isChecked():
            self.power = -(power_pct / 100) * self.power_limit
            self.power_flow_canvas.update_power_flow(-1, abs(self.power))
        self.power_label.setText(f"{abs(self.power):.1f} kW")
    
    def update_efficiency(self):
        """update efficiency values from spinners"""
        self.charging_efficiency = self.charging_eff_spinner.value() / 100
        self.discharging_efficiency = self.discharging_eff_spinner.value() / 100
    
    def update_battery_capacity(self, value):
        """update battery capacity"""
        self.battery_capacity = value
        self.battery_canvas.update_capacity(value)
        self.update_stats()
    
    def manual_soc_update(self, value):
        """manually update the soc value"""
        self.current_soc = value
        self.battery_canvas.update_soc(value, 0)
        self.update_stats()
    
    def change_sim_speed(self, index):
        """change simulation speed"""
        speeds = [1, 2, 5, 10]
        if index < len(speeds):
            self.time_step = speeds[index] / 60
            self.statusBar().showMessage(f"simulation running at {speeds[index]}x speed.")
    
    def toggle_simulation(self, checked):
        """pause or resume simulation"""
        if checked:
            self.sim_timer.stop()
            self.pause_button.setText("Resume")
            self.statusBar().showMessage("simulation paused.")
        else:
            self.sim_timer.start(1000)
            self.pause_button.setText("Pause")
            speed_text = self.speed_combo.currentText()
            self.statusBar().showMessage(f"simulation running at {speed_text}.")
    
    def reset_simulation(self):
        """reset the simulation to initial state"""
        self.current_soc = 80.0
        self.power = 0.0
        self.elapsed_time = 0
        self.idle_radio.setChecked(True)
        self.power_slider.setValue(0)
        self.soc_spinner.setValue(80.0)
        self.battery_canvas.soc_history = [80]
        self.battery_canvas.time_history = [0]
        self.battery_canvas.update_soc(80, 0)
        self.power_flow_canvas.update_power_flow(0, 0)
        self.update_stats()
        self.statusBar().showMessage("simulation reset.")
    
    def update_simulation(self):
        """update the simulation for one time step"""
        if self.power > 0:
            delta_soc = self.power * self.charging_efficiency / self.battery_capacity * self.time_step / 60 * 100
        elif self.power < 0:
            delta_soc = self.power / self.discharging_efficiency / self.battery_capacity * self.time_step / 60 * 100
        else:
            delta_soc = 0
        
        new_soc = self.current_soc + delta_soc
        new_soc = max(0, min(100, new_soc))
      
        if (new_soc == 0 and delta_soc < 0) or (new_soc == 100 and delta_soc > 0):
            self.power = 0
            self.idle_radio.setChecked(True)
            self.power_slider.setValue(0)
            self.power_flow_canvas.update_power_flow(0, 0)
            self.power_label.setText("0.0 kW")
          
        self.current_soc = new_soc
        self.elapsed_time += self.time_step * 60
        self.battery_canvas.update_soc(new_soc, self.time_step)
        self.update_stats()
    
    def closeEvent(self, event):
        if hasattr(self, 'sensor_manager') and self.sensors_connected:
            self.sensor_manager.disconnect_all()
        if hasattr(self, 'sim_timer'):
            self.sim_timer.stop()
        if hasattr(self, 'sensor_timer'):
            self.sensor_timer.stop()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = V2GSimulator()
    window.show()
    sys.exit(app.exec_())
