#!/usr/bin/env python3
"""
Smart Battery Monitor with AI Safety System
For Raspberry Pi 5 with MCP3008 ADC
"""

import sys
import time
import os
import datetime
import threading
from collections import deque

# Print debug information
print("Starting Smart Battery Monitor...")
print(f"Python version: {sys.version}")

# Try importing dependencies with error handling
try:
    print("Importing PyQt5...")
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QGroupBox, QFormLayout, QPushButton, QTabWidget
    )
    from PyQt5.QtCore import QTimer, pyqtSignal, QObject
    from PyQt5.QtGui import QFont
except ImportError as e:
    print(f"ERROR: PyQt5 import failed: {e}")
    print("Install with: pip install PyQt5")
    sys.exit(1)

try:
    print("Importing matplotlib...")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
except ImportError as e:
    print(f"ERROR: Matplotlib import failed: {e}")
    print("Install with: pip install matplotlib")
    sys.exit(1)

try:
    print("Importing numpy and pandas...")
    import numpy as np
    import pandas as pd
except ImportError as e:
    print(f"ERROR: numpy/pandas import failed: {e}")
    print("Install with: pip install numpy pandas")
    sys.exit(1)

try:
    print("Importing scikit-learn...")
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
except ImportError as e:
    print(f"ERROR: scikit-learn import failed: {e}")
    print("Install with: pip install scikit-learn")
    sys.exit(1)

try:
    print("Importing spidev...")
    import spidev
except ImportError as e:
    print(f"ERROR: spidev import failed: {e}")
    print("Install with: pip install spidev")
    print("Also ensure SPI is enabled in raspi-config")
    sys.exit(1)

try:
    print("Importing joblib...")
    import joblib
except ImportError as e:
    print(f"ERROR: joblib import failed: {e}")
    print("Install with: pip install joblib")
    sys.exit(1)

# Try to import GPIO libraries with fallback
try:
    print("Importing gpiod...")
    import gpiod
    using_gpiod = True
except ImportError:
    print("WARNING: gpiod import failed, trying RPi.GPIO as fallback...")
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        using_gpiod = False
    except ImportError as e:
        print(f"ERROR: Both gpiod and RPi.GPIO failed: {e}")
        print("Install with: pip install gpiod")
        print("or: pip install RPi.GPIO")
        sys.exit(1)

print("All imports successful!")

# GPIO setup with fallback
KILL_PIN = 26
if using_gpiod:
    try:
        print(f"Setting up gpiod on pin {KILL_PIN}...")
        chip = gpiod.Chip('gpiochip0')
        kill_line = chip.get_line(KILL_PIN)
        kill_line.request(
            consumer="battery_monitor",
            type=gpiod.LINE_REQ_DIR_OUT,
            default_vals=[0]
        )
        
        def set_kill_switch(value):
            kill_line.set_value(int(value))
    except Exception as e:
        print(f"ERROR: gpiod setup failed: {e}")
        print("Continuing with dummy GPIO...")
        
        def set_kill_switch(value):
            print(f"[DUMMY] Setting kill switch to {value}")
else:
    try:
        print(f"Setting up RPi.GPIO on pin {KILL_PIN}...")
        GPIO.setup(KILL_PIN, GPIO.OUT)
        GPIO.output(KILL_PIN, GPIO.LOW)
        
        def set_kill_switch(value):
            GPIO.output(KILL_PIN, GPIO.HIGH if value else GPIO.LOW)
    except Exception as e:
        print(f"ERROR: RPi.GPIO setup failed: {e}")
        print("Continuing with dummy GPIO...")
        
        def set_kill_switch(value):
            print(f"[DUMMY] Setting kill switch to {value}")

# AI signals class
class AISignals(QObject):
    soh_updated = pyqtSignal(float)
    anomaly_detected = pyqtSignal(float, bool)
    model_updated = pyqtSignal()
    log_event = pyqtSignal(str)

# Canvas classes
class BatteryCanvas(FigureCanvas):
    def __init__(self):
        print("Initializing Battery SOC Canvas...")
        fig = Figure(figsize=(5, 3), dpi=100)
        self.axes = fig.add_subplot(111)
        super().__init__(fig)

        self.soc_history = [0]
        self.time_history = [0]
        self.max_points = 300
        self.line, = self.axes.plot([], [], "-", linewidth=2)
        self.axes.set_xlim(0, self.max_points)
        self.axes.set_ylim(0, 100)
        self.axes.set_xlabel("Time (s)", fontsize=10)
        self.axes.set_ylabel("State of Charge (%)", fontsize=10)
        self.axes.set_title("Battery State of Charge", fontsize=12, fontweight='bold')
        self.axes.grid(True)
        self.soc_text = self.axes.text(
            0.02, 0.95, "SOC: 0%", transform=self.axes.transAxes
        )
        fig.tight_layout()

    def update_soc(self, soc, dt):
        try:
            # Apply 2-point moving average
            prev = self.soc_history[-1]
            avg_soc = (prev + soc) / 2

            t_new = self.time_history[-1] + dt
            self.time_history.append(t_new)
            self.soc_history.append(avg_soc)

            if len(self.soc_history) > self.max_points:
                self.soc_history = self.soc_history[-self.max_points:]
                self.time_history = self.time_history[-self.max_points:]

            self.line.set_data(self.time_history, self.soc_history)
            self.axes.set_xlim(self.time_history[0], self.time_history[-1] * 1.05)
            self.soc_text.set_text(f"SOC: {avg_soc:.1f}%")
            self.draw()
        except Exception as e:
            print(f"Error in update_soc: {e}")

class AnomalyCanvas(FigureCanvas):
    def __init__(self):
        print("Initializing Anomaly Canvas...")
        fig = Figure(figsize=(5, 3), dpi=100)
        self.axes = fig.add_subplot(111)
        super().__init__(fig)

        self.anomaly_history = [0]
        self.time_history = [0]
        self.max_points = 300
        self.line, = self.axes.plot([], [], "-r", linewidth=2)
        self.axes.set_xlim(0, self.max_points)
        self.axes.set_ylim(0, 1)
        self.axes.set_xlabel("Time (s)", fontsize=10)
        self.axes.set_ylabel("Anomaly Score", fontsize=10)
        self.axes.set_title("Battery Anomaly Detection", fontsize=12, fontweight='bold')
        self.axes.grid(True)
        self.axes.axhline(y=0.8, color='orange', linestyle='--')
        self.score_text = self.axes.text(
            0.02, 0.95, "Score: 0.0", transform=self.axes.transAxes
        )
        fig.tight_layout()

    def update_score(self, score, dt):
        try:
            t_new = self.time_history[-1] + dt
            self.time_history.append(t_new)
            self.anomaly_history.append(score)

            if len(self.anomaly_history) > self.max_points:
                self.anomaly_history = self.anomaly_history[-self.max_points:]
                self.time_history = self.time_history[-self.max_points:]

            self.line.set_data(self.time_history, self.anomaly_history)
            self.axes.set_xlim(self.time_history[0], self.time_history[-1] * 1.05)
            self.score_text.set_text(f"Score: {score:.3f}")
            self.draw()
        except Exception as e:
            print(f"Error in update_score: {e}")

class SOHCanvas(FigureCanvas):
    def __init__(self):
        print("Initializing SOH Canvas...")
        fig = Figure(figsize=(5, 3), dpi=100)
        self.axes = fig.add_subplot(111)
        super().__init__(fig)

        self.soh_history = [100]
        self.time_history = [0]
        self.max_points = 300
        self.line, = self.axes.plot([], [], "-g", linewidth=2)
        self.axes.set_xlim(0, self.max_points)
        self.axes.set_ylim(0, 100)
        self.axes.set_xlabel("Time (s)", fontsize=10)
        self.axes.set_ylabel("State of Health (%)", fontsize=10)
        self.axes.set_title("Battery Health Estimation", fontsize=12, fontweight='bold')
        self.axes.grid(True)
        self.soh_text = self.axes.text(
            0.02, 0.95, "SOH: 100%", transform=self.axes.transAxes
        )
        fig.tight_layout()

    def update_soh(self, soh, dt):
        try:
            t_new = self.time_history[-1] + dt
            self.time_history.append(t_new)
            self.soh_history.append(soh)

            if len(self.soh_history) > self.max_points:
                self.soh_history = self.soh_history[-self.max_points:]
                self.time_history = self.time_history[-self.max_points:]

            self.line.set_data(self.time_history, self.soh_history)
            self.axes.set_xlim(self.time_history[0], self.time_history[-1] * 1.05)
            self.soh_text.set_text(f"SOH: {soh:.1f}%")
            self.draw()
        except Exception as e:
            print(f"Error in update_soh: {e}")

# Battery AI class
class BatteryManagementAI:
    def __init__(self, voltage_pin, current_pin, temp_pin, 
                 voltage_red_limit, voltage_yellow_limit,
                 current_red_limit, current_yellow_limit, 
                 temp_red_limit, temp_yellow_limit,
                 sample_rate=1.0, history_size=1000, model_update_interval=86400,
                 log_directory="/home/pi/battery_logs/"):
        """
        Initialize the BatteryManagementAI system
        """
        print("Initializing BatteryManagementAI...")
        
        # Setup signals
        self.signals = AISignals()
        
        # ADC pin configuration
        self.voltage_pin = voltage_pin
        self.current_pin = current_pin
        self.temp_pin = temp_pin
        
        # Safety limits
        self.voltage_red_limit = voltage_red_limit
        self.voltage_yellow_limit = voltage_yellow_limit
        self.current_red_limit = current_red_limit
        self.current_yellow_limit = current_yellow_limit
        self.temp_red_limit = temp_red_limit
        self.temp_yellow_limit = temp_yellow_limit
        
        # System parameters
        self.sample_rate = sample_rate
        self.history_size = history_size
        self.model_update_interval = model_update_interval
        self.log_directory = log_directory
        
        # Ensure log directory exists
        try:
            if not os.path.exists(log_directory):
                os.makedirs(log_directory)
                print(f"Created log directory: {log_directory}")
        except Exception as e:
            print(f"WARNING: Failed to create log directory: {e}")
            self.log_directory = "./"  # Fallback to current directory
        
        # Data storage
        self.readings = pd.DataFrame(columns=['timestamp', 'voltage', 'current', 'temperature', 'soh', 'anomaly_score'])
        self.recent_readings = {'voltage': [], 'current': [], 'temperature': []}
        
        # Initialize models
        print("Initializing ML models...")
        self.scaler = StandardScaler()
        self.anomaly_detector = IsolationForest(contamination=0.05, random_state=42)
        self.soh_estimation = 100.0  # Initial State of Health
        
        # Load models if they exist
        self.load_models()
        
        # System state
        self.running = False
        self.connection_active = True
        print("BatteryManagementAI initialization complete.")
        
    def detect_anomalies(self, reading):
        """
        Use the anomaly detection model to identify unusual patterns
        
        Args:
            reading: Dictionary containing sensor readings
            
        Returns:
            Anomaly score and boolean indicating if anomaly detected
        """
        # Skip if we don't have enough data to normalize
        if len(self.readings) < 10:
            return 0, False
        
        try:
            # Format the data for prediction
            features = np.array([[
                reading['voltage'], 
                reading['current'], 
                reading['temperature']
            ]])
            
            # Normalize the data
            scaled_features = self.scaler.transform(features)
            
            # Get anomaly scores (-1 for anomalies, 1 for normal data)
            # Convert to 0-1 scale where higher values are more anomalous
            score = -self.anomaly_detector.decision_function(scaled_features)[0]
            normalized_score = (score + 1) / 2  # Convert from [-1,1] to [0,1]
            
            # Consider it an anomaly if score is above 0.8 (very unusual)
            is_anomaly = normalized_score > 0.8
            
            # Emit signal with result
            self.signals.anomaly_detected.emit(normalized_score, is_anomaly)
            
            return normalized_score, is_anomaly
        except Exception as e:
            print(f"Error in detect_anomalies: {e}")
            return 0, False
    
    def estimate_soh(self, voltage, current):
        """
        Estimate the State of Health of the battery based on recent data
        
        Returns:
            SOH value (0-100%)
        """
        if len(self.readings) < 100:
            return self.soh_estimation
            
        try:
            # Simple SOH estimation based on voltage and internal resistance trends
            # Get the last 100 readings
            recent_data = self.readings.tail(100)
            
            # Calculate voltage sag under load (crude internal resistance estimation)
            avg_voltage = recent_data['voltage'].mean()
            nominal_voltage = 12.0  # Nominal voltage for a 12V battery
            
            # Decay rate - real implementation would use actual characterization
            voltage_factor = min(1.0, avg_voltage / nominal_voltage)
            
            # Adjust SOH estimation (simple decay model)
            new_soh = self.soh_estimation * 0.999  # Slow natural decay
            new_soh *= (0.8 + 0.2 * voltage_factor)  # Adjust based on voltage health
            
            # Limit to reasonable range
            new_soh = max(0.0, min(100.0, new_soh))
            
            # Emit signal with updated SOH
            self.signals.soh_updated.emit(new_soh)
            
            return new_soh
        except Exception as e:
            print(f"Error in estimate_soh: {e}")
            return self.soh_estimation
    
    def update_models(self):
        """
        Periodically update the anomaly detection model
        """
        if len(self.readings) < 100:
            return
            
        try:
            print("Updating AI models...")
            # Get feature data
            features = self.readings[['voltage', 'current', 'temperature']].values
            
            # Update the scaler
            self.scaler.fit(features)
            scaled_features = self.scaler.transform(features)
            
            # Update the anomaly detector
            self.anomaly_detector.fit(scaled_features)
            
            # Save the updated models
            self.save_models()
            
            # Emit signal
            self.signals.model_updated.emit()
            self.signals.log_event.emit("Models updated successfully")
            print("AI models updated successfully.")
        except Exception as e:
            error_msg = f"Error updating models: {e}"
            print(error_msg)
            self.signals.log_event.emit(error_msg)
    
    def save_models(self):
        """Save trained models to disk"""
        try:
            model_path = os.path.join(self.log_directory, 'models')
            if not os.path.exists(model_path):
                os.makedirs(model_path)
                
            joblib.dump(self.scaler, os.path.join(model_path, 'scaler.pkl'))
            joblib.dump(self.anomaly_detector, os.path.join(model_path, 'anomaly_detector.pkl'))
            
            # Save metadata 
            with open(os.path.join(model_path, 'soh.txt'), 'w') as f:
                f.write(f"{self.soh_estimation}")
                
            print(f"Models saved to {model_path}")
        except Exception as e:
            print(f"Error saving models: {e}")
    
    def load_models(self):
        """Load trained models from disk if they exist"""
        try:
            model_path = os.path.join(self.log_directory, 'models')
            
            if not os.path.exists(model_path):
                print("No existing models found. Starting with new models.")
                return
                
            scaler_path = os.path.join(model_path, 'scaler.pkl')
            detector_path = os.path.join(model_path, 'anomaly_detector.pkl')
            soh_path = os.path.join(model_path, 'soh.txt')
            
            if os.path.exists(scaler_path):
                self.scaler = joblib.load(scaler_path)
                print("Loaded scaler model.")
                
            if os.path.exists(detector_path):
                self.anomaly_detector = joblib.load(detector_path)
                print("Loaded anomaly detector model.")
                
            if os.path.exists(soh_path):
                with open(soh_path, 'r') as f:
                    self.soh_estimation = float(f.read().strip())
                print(f"Loaded SOH estimation: {self.soh_estimation}%")
        except Exception as e:
            print(f"Error loading models: {e}")
    
    def add_reading(self, voltage, current, temperature):
        """Add a new sensor reading to the dataset"""
        try:
            # Get current timestamp
            timestamp = datetime.datetime.now()
            
            # Detect anomalies
            anomaly_score, is_anomaly = self.detect_anomalies({
                'voltage': voltage,
                'current': current,
                'temperature': temperature
            })
            
            # Update SOH periodically
            if len(self.readings) % 100 == 0:
                self.soh_estimation = self.estimate_soh(voltage, current)
            
            # Store the data
            new_row = pd.DataFrame({
                'timestamp': [timestamp],
                'voltage': [voltage],
                'current': [current],
                'temperature': [temperature],
                'soh': [self.soh_estimation],
                'anomaly_score': [anomaly_score]
            })
            
            self.readings = pd.concat([self.readings, new_row])
            
            # Keep only the latest history_size readings
            if len(self.readings) > self.history_size:
                self.readings = self.readings.tail(self.history_size)
                
            return anomaly_score, is_anomaly, self.soh_estimation
        except Exception as e:
            print(f"Error in add_reading: {e}")
            return 0, False, self.soh_estimation

# Log viewer widget
class LogViewer(QWidget):
    def __init__(self):
        super().__init__()
        print("Initializing Log Viewer...")
        layout = QVBoxLayout(self)
        
        self.log_label = QLabel("System Event Log")
        self.log_label.setFont(QFont("Monospace", 12, QFont.Bold))
        layout.addWidget(self.log_label)
        
        self.log_text = QLabel()
        self.log_text.setFont(QFont("Monospace", 10))
        self.log_text.setStyleSheet("background-color: black; color: green; padding: 10px;")
        self.log_text.setWordWrap(True)
        layout.addWidget(self.log_text)
        
        self.clear_button = QPushButton("Clear Log")
        self.clear_button.clicked.connect(self.clear_log)
        layout.addWidget(self.clear_button)
        
        self.log_entries = []
        self.max_entries = 100

    def add_log_entry(self, entry):
        try:
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {entry}"
            self.log_entries.append(log_entry)
            print(f"LOG: {log_entry}")
            
            # Keep only the latest entries
            if len(self.log_entries) > self.max_entries:
                self.log_entries.pop(0)
                
            self.update_display()
        except Exception as e:
            print(f"Error in add_log_entry: {e}")
    
    def update_display(self):
        try:
            self.log_text.setText("<br>".join(self.log_entries))
        except Exception as e:
            print(f"Error in update_display: {e}")
    
    def clear_log(self):
        try:
            self.log_entries = []
            self.update_display()
        except Exception as e:
            print(f"Error in clear_log: {e}")

# Main window
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        print("Initializing Main Window...")
        self.setWindowTitle("Smart Battery Monitor with AI Safety System")
        self.setGeometry(50, 50, 800, 600)

        # Setup tabs
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Main tab
        self.main_tab = QWidget()
        self.main_layout = QVBoxLayout(self.main_tab)
        self.tabs.addTab(self.main_tab, "Main Dashboard")
        
        # AI tab
        self.ai_tab = QWidget()
        self.ai_layout = QVBoxLayout(self.ai_tab)
        self.tabs.addTab(self.ai_tab, "AI Monitoring")
        
        # Log tab
        self.log_viewer = LogViewer()
        self.tabs.addTab(self.log_viewer, "System Log")
        
        # SOC plot in main tab
        self.canvas = BatteryCanvas()
        self.main_layout.addWidget(self.canvas)

        # ADC readings + status
        box = QGroupBox("Battery Sensor Readings")
        form = QFormLayout()
        big = QFont(); big.setPointSize(14)
        big_bold = QFont(); big_bold.setPointSize(14); big_bold.setBold(True)

        lbl_batt_v  = QLabel("Battery Voltage (V):"); lbl_batt_v.setFont(big_bold)
        lbl_curr    = QLabel("Load Current (A):");    lbl_curr.setFont(big_bold)
        lbl_temp    = QLabel("Temperature (°F):");    lbl_temp.setFont(big_bold)
        lbl_v_stat  = QLabel("Voltage Status:");      lbl_v_stat.setFont(big_bold)
        lbl_i_stat  = QLabel("Current Status:");      lbl_i_stat.setFont(big_bold)
        lbl_t_stat  = QLabel("Temperature Status:");  lbl_t_stat.setFont(big_bold)

        self.voltage_label  = QLabel("N/A"); self.voltage_label.setFont(big)
        self.current_label  = QLabel("N/A"); self.current_label.setFont(big)
        self.temp_label     = QLabel("N/A"); self.temp_label.setFont(big)
        self.voltage_status = QLabel("OK");  self.voltage_status.setFont(big)
        self.current_status = QLabel("OK");  self.current_status.setFont(big)
        self.temp_status    = QLabel("OK");  self.temp_status.setFont(big)

        form.addRow(lbl_batt_v, self.voltage_label)
        form.addRow(lbl_v_stat, self.voltage_status)
        form.addRow(lbl_curr,   self.current_label)
        form.addRow(lbl_i_stat, self.current_status)
        form.addRow(lbl_temp,   self.temp_label)
        form.addRow(lbl_t_stat, self.temp_status)

        box.setLayout(form)
        self.main_layout.addWidget(box)
        
        # AI Status in main tab
        ai_box = QGroupBox("AI Safety System Status")
        ai_form = QFormLayout()
        
        lbl_soh = QLabel("Battery Health (SOH):");  lbl_soh.setFont(big_bold)
        lbl_anomaly = QLabel("Anomaly Score:");     lbl_anomaly.setFont(big_bold)
        lbl_ai_stat = QLabel("AI System Status:");  lbl_ai_stat.setFont(big_bold)
        
        self.soh_label = QLabel("100.0%"); self.soh_label.setFont(big)
        self.anomaly_label = QLabel("0.000"); self.anomaly_label.setFont(big)
        self.ai_status_label = QLabel("NORMAL"); self.ai_status_label.setFont(big)
        self.ai_status_label.setStyleSheet("color: green;")
        
        ai_form.addRow(lbl_soh, self.soh_label)
        ai_form.addRow(lbl_anomaly, self.anomaly_label)
        ai_form.addRow(lbl_ai_stat, self.ai_status_label)
        
        ai_box.setLayout(ai_form)
        self.main_layout.addWidget(ai_box)
        
        # AI tab with plots
        self.anomaly_canvas = AnomalyCanvas()
        self.ai_layout.addWidget(self.anomaly_canvas)
        
        self.soh_canvas = SOHCanvas()
        self.ai_layout.addWidget(self.soh_canvas)
        
        # AI model info
        model_box = QGroupBox("AI Model Information")
        model_form = QFormLayout()
        
        lbl_model_status = QLabel("Model Status:"); lbl_model_status.setFont(big_bold)
        lbl_last_update = QLabel("Last Updated:"); lbl_last_update.setFont(big_bold)
        lbl_data_points = QLabel("Data Points:"); lbl_data_points.setFont(big_bold)
        
        self.model_status_label = QLabel("LOADED"); self.model_status_label.setFont(big)
        self.last_update_label = QLabel("N/A"); self.last_update_label.setFont(big)
        self.data_points_label = QLabel("0"); self.data_points_label.setFont(big)
        
        model_form.addRow(lbl_model_status, self.model_status_label)
        model_form.addRow(lbl_last_update, self.last_update_label)
        model_form.addRow(lbl_data_points, self.data_points_label)
        
        model_box.setLayout(model_form)
        self.ai_layout.addWidget(model_box)

        # SPI/MCP3008 setup with error handling
        try:
            print("Setting up SPI for MCP3008...")
            self.spi = spidev.SpiDev()
            self.spi.open(0, 0)
            self.spi.max_speed_hz = 1_350_000
            self.spi.mode = 0b00
        except Exception as e:
            print(f"WARNING: SPI setup failed: {e}")
            print("Using dummy ADC for simulation.")
            self.spi = None
            self.log_viewer.add_log_entry("ERROR: SPI initialization failed, using simulated values")

        # battery pack bounds
        self.volt_min = 11.2
        self.volt_max = 14.6

        # safety thresholds
        self.MAX_TEMP    = 70.0;  self.RED_TEMP    = 80.0
        self.MAX_CURRENT = 4.0;   self.RED_CURRENT = 4.5
        self.MAX_VOLTAGE = 14.0;  self.RED_VOLTAGE = 14.5

        # rolling buffers
        size = 5
        self.buf_t = deque(maxlen=size)
        self.buf_i = deque(maxlen=size)
        self.buf_v = deque(maxlen=size)
        
        # State tracking
        self.last_was_red = False
        self.last_was_yellow = False
        
        # Initialize AI system
        print("Initializing AI system...")
        self.ai_system = BatteryManagementAI(
            voltage_pin=2,
            current_pin=4,
            temp_pin=3,
            voltage_red_limit=self.RED_VOLTAGE,
            voltage_yellow_limit=self.MAX_VOLTAGE,
            current_red_limit=self.RED_CURRENT,
            current_yellow_limit=self.MAX_CURRENT,
            temp_red_limit=self.RED_TEMP,
            temp_yellow_limit=self.MAX_TEMP,
            sample_rate=0.5,
            history_size=5000  # Reduced from 10000 for better performance
        )
        
        # Connect AI signals
        self.ai_system.signals.soh_updated.connect(self.update_soh)
        self.ai_system.signals.anomaly_detected.connect(self.update_anomaly)
        self.ai_system.signals.model_updated.connect(self.model_updated)
        self.ai_system.signals.log_event.connect(self.log_event)
        
        # Set last model update time
        self.last_model_update = time.time()
        
        # Start background thread for model updates
        self.start_model_updater()
        
        # Log system startup
        self.log_event("Smart Battery Monitor System started")
        
        # start periodic updates (every 1 second - increased from 0.5 for better performance)
        self.sample_dt = 1.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_readings)
        self.timer.start(int(self.sample_dt * 1000))
        
        print("Main window initialization complete.")

    def read_raw(self, ch):
        """Read raw ADC value with dummy mode fallback"""
        if not (0 <= ch <= 7):
            return 0
            
        if self.spi is None:
            # Dummy mode - simulate reasonable values with some noise
            import random
            if ch == 2:  # Voltage channel
                return int((12.5 + random.uniform(-0.3, 0.3)) * (1024.0 / self.volt_max))
            elif ch == 3:  # Temperature channel
                temp_c = 35 + random.uniform(-5, 5)  # ~35°C with noise
                v_out = (temp_c - 25) / 100 + 0.75
                return int(v_out * 1024.0 / 5.0)
            elif ch == 4:  # Current channel
                current = 2.0 + random.uniform(-0.5, 0.5)  # ~2A with noise
                v_out = 2.5 + current * 0.1375
                return int(v_out * 1024.0 / 5.0)
            else:
                return random.randint(0, 1023)
        
        try:
            r = self.spi.xfer2([1, (8 + ch) << 4, 0])
            return ((r[1] & 3) << 8) + r[2]
        except Exception as e:
            print(f"Error reading ADC: {e}")
            # Fall back to dummy values if SPI fails
            return self.read_raw(ch)

    @staticmethod
    def colour_for(val, buf, max_l, red_l) -> str:
        if val > red_l:
            return "red"
        if len(buf) == buf.maxlen and sum(buf)/len(buf) > max_l:
            return "orange"
        return "green"

    def update_readings(self):
        try:
            # --- read sensors ---
            r_t = self.read_raw(3)
            v_t = r_t / 1024.0 * 5.0
            t_c = 100*(v_t - 0.75) + 25
            t_f = t_c * 9/5 + 32
            self.temp_label.setText(f"{t_f:.1f} °F")

            r_i = self.read_raw(4)
            v_i = r_i / 1024.0 * 5.0
            i_a = (v_i - 2.5)/0.1375 - 1
            self.current_label.setText(f"{i_a:.2f} A")

            r_v = self.read_raw(2)
            v_s = r_v / 1024.0 * 5.0
            b_v = v_s * (self.volt_max / 5.0)
            self.voltage_label.setText(f"{b_v:.2f} V")

            # SOC calculation
            soc = (b_v - self.volt_min)/(self.volt_max - self.volt_min)*100
            soc = max(0, min(100, soc))
            self.canvas.update_soc(soc, self.sample_dt)

            # safety logic - basic thresholds
            red = (t_c > self.RED_TEMP) or (i_a > self.RED_CURRENT) or (b_v > self.RED_VOLTAGE)
            self.buf_t.append(t_c); self.buf_i.append(i_a); self.buf_v.append(b_v)

            if len(self.buf_t) == self.buf_t.maxlen:
                at = sum(self.buf_t)/len(self.buf_t)
                ai = sum(self.buf_i)/len(self.buf_i)
                av = sum(self.buf_v)/len(self.buf_v)
                yellow = (at > self.MAX_TEMP) or (ai > self.MAX_CURRENT) or (av > self.MAX_VOLTAGE)
            else:
                yellow = False

            # AI processing
            anomaly_score, is_anomaly, soh = self.ai_system.add_reading(b_v, i_a, t_c)
            
            # Update SOH display if we have a new one
            self.soh_label.setText(f"{soh:.1f}%")
            
            # Update anomaly score display
            self.anomaly_label.setText(f"{anomaly_score:.3f}")
            if is_anomaly:
                self.anomaly_label.setStyleSheet("color: red; font-weight: bold;")
                self.ai_status_label.setText("ANOMALY DETECTED")
                self.ai_status_label.setStyleSheet("color: red; font-weight: bold;")
                self.log_event(f"ANOMALY DETECTED! Score: {anomaly_score:.3f}")
            elif anomaly_score > 0.5:
                self.anomaly_label.setStyleSheet("color: orange;")
                self.ai_status_label.setText("UNUSUAL PATTERN")
                self.ai_status_label.setStyleSheet("color: orange;")
            else:
                self.anomaly_label.setStyleSheet("color: green;")
                self.ai_status_label.setText("NORMAL")
                self.ai_status_label.setStyleSheet("color: green;")
            
            # Combined safety decision (traditional + AI)
            combined_red = red or is_anomaly
            combined_yellow = yellow or (anomaly_score > 0.5)
            
            # Update safety status displays
            col_t = self.colour_for(t_c, self.buf_t, self.MAX_TEMP, self.RED_TEMP)
            col_i = self.colour_for(i_a, self.buf_i, self.MAX_CURRENT, self.RED_CURRENT)
            col_v = self.colour_for(b_v, self.buf_v, self.MAX_VOLTAGE, self.RED_VOLTAGE)

            self.temp_label.setStyleSheet(f"color:{col_t};")
            self.current_label.setStyleSheet(f"color:{col_i};")
            self.voltage_label.setStyleSheet(f"color:{col_v};")

            self.temp_status.setText(col_t.upper())
            self.current_status.setText(col_i.upper())
            self.voltage_status.setText(col_v.upper())
            
            # Update AI charts
            self.anomaly_canvas.update_score(anomaly_score, self.sample_dt)
            self.soh_canvas.update_soh(soh, self.sample_dt)
            
            # Update data points count
            self.data_points_label.setText(str(len(self.ai_system.readings)))
            
            # Set kill switch based on combined safety decision
            set_kill_switch(combined_red)
            
            # Log severe safety events
            if combined_red and not self.last_was_red:
                self.log_event(f"EMERGENCY SHUTDOWN - V:{b_v:.2f}V, I:{i_a:.2f}A, T:{t_c:.1f}°C, Anomaly:{anomaly_score:.3f}")
            elif combined_yellow and not self.last_was_yellow:
                self.log_event(f"WARNING CONDITION - V:{b_v:.2f}V, I:{i_a:.2f}A, T:{t_c:.1f}°C, Anomaly:{anomaly_score:.3f}")
                
            self.last_was_red = combined_red
            self.last_was_yellow = combined_yellow
            
        except Exception as e:
            print(f"Error in update_readings: {e}")
            self.log_event(f"Error updating readings: {e}")

    def start_model_updater(self):
        """Start background thread for model updates"""
        try:
            self.updater_thread = threading.Thread(target=self.model_updater_thread)
            self.updater_thread.daemon = True
            self.updater_thread.start()
            print("Model updater thread started.")
        except Exception as e:
            print(f"Error starting model updater thread: {e}")
        
    def model_updater_thread(self):
        """Background thread that periodically updates the AI models"""
        try:
            while True:
                # Sleep for one hour between updates
                time.sleep(3600)
                
                # Only update if we have enough data
                if len(self.ai_system.readings) >= 100:
                    print("Scheduled model update initiated.")
                    self.ai_system.update_models()
                    self.last_model_update = time.time()
                    self.last_update_label.setText(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        except Exception as e:
            print(f"Error in model updater thread: {e}")
                
    def update_soh(self, soh):
        """Called when the AI system updates the SOH estimate"""
        try:
            self.soh_label.setText(f"{soh:.1f}%")
            
            # Color-code by health level
            if soh < 50:
                self.soh_label.setStyleSheet("color: red;")
            elif soh < 80:
                self.soh_label.setStyleSheet("color: orange;")
            else:
                self.soh_label.setStyleSheet("color: green;")
        except Exception as e:
            print(f"Error updating SOH: {e}")
            
    def update_anomaly(self, score, is_anomaly):
        """Called when the AI system detects an anomaly"""
        # Additional processing can be done here
        pass
        
    def model_updated(self):
        """Called when the AI model is updated"""
        try:
            self.model_status_label.setText("UPDATED")
            self.model_status_label.setStyleSheet("color: green; font-weight: bold;")
            self.last_update_label.setText(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        except Exception as e:
            print(f"Error in model_updated: {e}")
        
    def log_event(self, message):
        """Log a system event"""
        self.log_viewer.add_log_entry(message)

    def closeEvent(self, event):
        """Clean up when closing the application"""
        try:
            # Reset kill switch
            set_kill_switch(False)
            
            # Save AI model data
            self.ai_system.save_models()
            self.log_event("System shutdown - models saved")
            
            event.accept()
        except Exception as e:
            print(f"Error during shutdown: {e}")

# Main execution block with error handling
if __name__ == "__main__":
    try:
        print("Starting application...")
        app = QApplication(sys.argv)
        w = MainWindow()
        w.show()
        print("Application running.")
        sys.exit(app.exec_())
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        # Try to save a crash log
        try:
            with open("battery_monitor_crash.log", "a") as f:
                f.write(f"[{datetime.datetime.now()}] CRASH: {e}\n")
        except:
            pass
        sys.exit(1)