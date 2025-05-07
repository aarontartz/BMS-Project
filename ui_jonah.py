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
import csv
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
        
        def set_kill_switch(value):
            print(f"[DUMMY] Setting kill switch to {value}")

# ---------------------------------------------------------------------------
#  Classes (AISignals, BatteryCanvas, AnomalyCanvas, SOHCanvas, BatteryManagementAI)
#  UNCHANGED – omitted for brevity
# ---------------------------------------------------------------------------

# (Paste your original AISignals, BatteryCanvas, AnomalyCanvas, SOHCanvas,
#  and BatteryManagementAI definitions here with NO modifications.)

# ---------------------------------------------------------------------------
#  LogViewer class (UNCHANGED)
# ---------------------------------------------------------------------------

# (Paste original LogViewer definition here.)

# ---------------------------------------------------------------------------
#  Main window
# ---------------------------------------------------------------------------
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
        
        # Manual Killswitch Control
        self.manual_killswitch_active = False
        self.killswitch_box = QGroupBox("Emergency Killswitch")
        killswitch_layout = QVBoxLayout()
        
        # Status indicator
        self.killswitch_status = QLabel("Killswitch Status: NORMAL")
        self.killswitch_status.setFont(QFont("Arial", 14, QFont.Bold))
        self.killswitch_status.setStyleSheet("color: green;")
        killswitch_layout.addWidget(self.killswitch_status)
        
        # Control button  (⇣ only minimal edits here)
        self.killswitch_button = QPushButton("EMERGENCY KILLSWITCH")
        self.killswitch_button.setCheckable(True)                    # make it latched
        self.killswitch_button.setMinimumHeight(50)
        self.killswitch_button.setFont(QFont("Arial", 14, QFont.Bold))
        self.killswitch_button.setStyleSheet(
            "QPushButton {background-color: red;  color: white; font-weight: bold; padding: 10px;}"
            "QPushButton:checked {background-color: #550000;}"       # darker when engaged
        )
        self.killswitch_button.toggled.connect(self.toggle_killswitch)  # use toggled
        killswitch_layout.addWidget(self.killswitch_button)
        
        killswitch_layout.addWidget(QLabel("Press to manually activate/deactivate the killswitch"))
        
        self.killswitch_box.setLayout(killswitch_layout)
        self.main_layout.addWidget(self.killswitch_box)
        
        # -------------------------------------------------------------------
        #  Rest of __init__ is UNCHANGED (plots, labels, AI init, timers, …)
        #  Paste the remainder of your original __init__ exactly as‑is.
        # -------------------------------------------------------------------

        # *** START of code identical to your original after killswitch box ***
        # SOC plot in main tab
        self.canvas = BatteryCanvas()
        self.main_layout.addWidget(self.canvas)
        # (… keep everything else from your original __init__ down to the end)
        # *** END identical code ***

    # -----------------------------------------------------------------------
    #  Method modifications
    # -----------------------------------------------------------------------
    def toggle_killswitch(self, checked):
        """Latch/un‑latch the manual killswitch."""
        try:
            self.manual_killswitch_active = checked

            if checked:
                self.killswitch_status.setText("Killswitch Status: MANUALLY ENGAGED")
                self.killswitch_status.setStyleSheet("color: red; font-weight: bold;")
                self.killswitch_button.setText("RELEASE KILLSWITCH")
                self.log_event("MANUAL KILLSWITCH ENGAGED by user")
            else:
                self.killswitch_status.setText("Killswitch Status: NORMAL")
                self.killswitch_status.setStyleSheet("color: green;")
                self.killswitch_button.setText("EMERGENCY KILLSWITCH")
                self.log_event("MANUAL KILLSWITCH RELEASED by user")
        except Exception as e:
            print(f"Error toggling killswitch: {e}")
            self.log_event(f"Error toggling killswitch: {e}")

    def update_readings(self):
        try:
            # --- original sensor reading logic here (UNMODIFIED) ---
            # (Paste the entire body of your original update_readings up to the
            #  point just before 'combined_red' is set.)
            # -------------------------------------------------------

            # Combined safety decision (traditional + AI + manual latch)
            combined_red = red or is_anomaly or self.manual_killswitch_active

            # Update safety status displays (UNCHANGED)
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
            
            # Drive GPIO based on final decision
            set_kill_switch(combined_red)
            
            # Log severe safety events (UNCHANGED)
            if combined_red and not self.last_was_red:
                self.log_event(f"EMERGENCY SHUTDOWN - V:{b_v:.2f}V, I:{i_a:.2f}A, T:{t_c:.1f}°C, Anomaly:{anomaly_score:.3f}")
            elif combined_yellow and not self.last_was_yellow:
                self.log_event(f"WARNING CONDITION - V:{b_v:.2f}V, I:{i_a:.2f}A, T:{t_c:.1f}°C, Anomaly:{anomaly_score:.3f}")
                
            self.last_was_red = combined_red
            self.last_was_yellow = combined_yellow
        except Exception as e:
            print(f"Error in update_readings: {e}")
            self.log_event(f"Error updating readings: {e}")

    # (All other methods – start_model_updater, model_updater_thread, etc. –
    #  remain exactly as in your original file with NO changes.)

# ---------------------------------------------------------------------------
#  Main execution block (UNCHANGED)
# ---------------------------------------------------------------------------
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
        try:
            with open("battery_monitor_crash.log", "a") as f:
                f.write(f"[{datetime.datetime.now()}] CRASH: {e}\n")
        except:
            pass
        sys.exit(1)
