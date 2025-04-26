import numpy as np
import pandas as pd
import joblib
import time
import RPi.GPIO as GPIO
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import threading
import datetime
import os

class BatteryManagementAI:
    def __init__(self, relay_pin, voltage_pin, current_pin, temp_pin, 
                 voltage_red_limit, voltage_yellow_limit,
                 current_red_limit, current_yellow_limit, 
                 temp_red_limit, temp_yellow_limit,
                 sample_rate=1.0, history_size=1000, model_update_interval=86400,
                 log_directory="/home/pi/battery_logs/"):
        """
        Initialize the BatteryManagementAI system
        
        Args:
            relay_pin: GPIO pin connected to relay
            voltage_pin, current_pin, temp_pin: ADC pins for sensors
            *_red_limit, *_yellow_limit: Safety thresholds
            sample_rate: Sampling frequency in seconds
            history_size: Number of data points to keep in memory
            model_update_interval: Time between model updates in seconds (default: 1 day)
            log_directory: Where to store logs and models
        """
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(relay_pin, GPIO.OUT)
        self.relay_pin = relay_pin
        
        # Pin configuration
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
        if not os.path.exists(log_directory):
            os.makedirs(log_directory)
        
        # Data storage
        self.readings = pd.DataFrame(columns=['timestamp', 'voltage', 'current', 'temperature', 'soh', 'anomaly_score'])
        self.recent_readings = {'voltage': [], 'current': [], 'temperature': []}
        
        # Initialize models
        self.scaler = StandardScaler()
        self.anomaly_detector = IsolationForest(contamination=0.05, random_state=42)
        self.soh_estimation = 100.0  # Initial State of Health
        
        # Load models if they exist
        self.load_models()
        
        # System state
        self.running = False
        self.connection_active = True
        
    def read_sensors(self):
        """
        Read data from all sensors and return formatted values
        
        Returns:
            Dictionary with voltage, current, and temperature readings
        """
        # Simulating ADC readings - replace with actual sensor code
        # For a real implementation, use appropriate libraries for your sensor hardware
        try:
            # Read voltage (example conversion from ADC to voltage)
            voltage_raw = self._read_adc(self.voltage_pin)
            voltage = voltage_raw * (15.0 / 1023.0)  # Example conversion
            
            # Read current (example using LEM sensor)
            current_raw = self._read_adc(self.current_pin)
            current = (current_raw - 512) * 0.1  # Example conversion
            
            # Read temperature
            temp_raw = self._read_adc(self.temp_pin)
            temperature = temp_raw * 0.1  # Example conversion
            
            return {
                'voltage': voltage,
                'current': current,
                'temperature': temperature
            }
        except Exception as e:
            self.log_event(f"Sensor reading error: {str(e)}")
            return None
    
    def _read_adc(self, pin):
        """
        Read from ADC - placeholder for actual implementation
        In real usage, replace with code for your specific ADC
        """
        # Replace with actual ADC reading code for your hardware
        # This is just a simulation returning reasonable values
        import random
        
        if pin == self.voltage_pin:
            # Simulate voltage around 12V
            return random.uniform(11.5, 12.5) * (1023/15.0)
        elif pin == self.current_pin:
            # Simulate current around 1A with occasional spikes
            return random.uniform(0.8, 1.2) * 10 + 512
        elif pin == self.temp_pin:
            # Simulate temperature around 30°C
            return random.uniform(25, 35) * 10
        else:
            return 0
    
    def apply_safety_rules(self, reading):
        """
        Apply the basic safety rules to determine if connection should be severed
        
        Args:
            reading: Dictionary containing sensor readings
            
        Returns:
            Boolean indicating if connection should remain active
        """
        # Red limit checks - immediate action
        if (reading['voltage'] > self.voltage_red_limit or 
            reading['current'] > self.current_red_limit or 
            reading['temperature'] > self.temp_red_limit):
            self.log_event(f"RED LIMIT BREACH: V={reading['voltage']}, I={reading['current']}, T={reading['temperature']}")
            return False
        
        # Update recent readings lists (keep last 5)
        for key in self.recent_readings:
            self.recent_readings[key].append(reading[key])
            if len(self.recent_readings[key]) > 5:
                self.recent_readings[key].pop(0)
        
        # Yellow limit checks - based on averages of last 5 readings
        if len(self.recent_readings['voltage']) == 5:
            avg_voltage = sum(self.recent_readings['voltage']) / 5
            avg_current = sum(self.recent_readings['current']) / 5
            avg_temp = sum(self.recent_readings['temperature']) / 5
            
            if (avg_voltage > self.voltage_yellow_limit or 
                avg_current > self.current_yellow_limit or 
                avg_temp > self.temp_yellow_limit):
                self.log_event(f"YELLOW LIMIT BREACH: Avg V={avg_voltage}, Avg I={avg_current}, Avg T={avg_temp}")
                return False
        
        return True
    
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
        
        return normalized_score, is_anomaly
    
    def estimate_soh(self):
        """
        Estimate the State of Health of the battery based on recent data
        
        Returns:
            SOH value (0-100%)
        """
        if len(self.readings) < 100:
            return self.soh_estimation
            
        # Simple SOH estimation based on voltage and internal resistance trends
        # For actual implementation, use more sophisticated algorithms
        
        # Get the last 100 readings
        recent_data = self.readings.tail(100)
        
        # Calculate voltage sag under load (crude internal resistance estimation)
        # This is a simplified approach - real implementation would be more sophisticated
        avg_voltage = recent_data['voltage'].mean()
        nominal_voltage = 12.0  # Nominal voltage for a 12V battery
        
        # Decay rate - real implementation would use actual characterization
        voltage_factor = min(1.0, avg_voltage / nominal_voltage)
        
        # Adjust SOH estimation (simple decay model)
        new_soh = self.soh_estimation * 0.999  # Slow natural decay
        new_soh *= (0.8 + 0.2 * voltage_factor)  # Adjust based on voltage health
        
        # Limit to reasonable range
        new_soh = max(0.0, min(100.0, new_soh))
        
        return new_soh
    
    def update_models(self):
        """
        Periodically update the anomaly detection model
        """
        if len(self.readings) < 100:
            return
            
        try:
            # Get feature data
            features = self.readings[['voltage', 'current', 'temperature']].values
            
            # Update the scaler
            self.scaler.fit(features)
            scaled_features = self.scaler.transform(features)
            
            # Update the anomaly detector
            self.anomaly_detector.fit(scaled_features)
            
            # Save the updated models
            self.save_models()
            
            self.log_event("Models updated successfully")
        except Exception as e:
            self.log_event(f"Error updating models: {str(e)}")
    
    def save_models(self):
        """Save trained models to disk"""
        model_path = os.path.join(self.log_directory, 'models')
        if not os.path.exists(model_path):
            os.makedirs(model_path)
            
        joblib.dump(self.scaler, os.path.join(model_path, 'scaler.pkl'))
        joblib.dump(self.anomaly_detector, os.path.join(model_path, 'anomaly_detector.pkl'))
        
        # Save metadata 
        with open(os.path.join(model_path, 'soh.txt'), 'w') as f:
            f.write(f"{self.soh_estimation}")
    
    def load_models(self):
        """Load trained models from disk if they exist"""
        model_path = os.path.join(self.log_directory, 'models')
        
        if not os.path.exists(model_path):
            return
            
        scaler_path = os.path.join(model_path, 'scaler.pkl')
        detector_path = os.path.join(model_path, 'anomaly_detector.pkl')
        soh_path = os.path.join(model_path, 'soh.txt')
        
        if os.path.exists(scaler_path):
            self.scaler = joblib.load(scaler_path)
            
        if os.path.exists(detector_path):
            self.anomaly_detector = joblib.load(detector_path)
            
        if os.path.exists(soh_path):
            with open(soh_path, 'r') as f:
                self.soh_estimation = float(f.read().strip())
    
    def log_event(self, message):
        """Log system events with timestamp"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        
        print(log_message)
        
        # Write to log file
        log_file = os.path.join(self.log_directory, 
                               f"battery_log_{datetime.datetime.now().strftime('%Y%m%d')}.txt")
        
        with open(log_file, 'a') as f:
            f.write(log_message + "\n")
    
    def control_relay(self, state):
        """
        Control the relay state
        
        Args:
            state: True to connect, False to disconnect
        """
        GPIO.output(self.relay_pin, state)
        self.connection_active = state
        
        status = "CONNECTED" if state else "DISCONNECTED"
        self.log_event(f"Battery connection {status}")
    
    def background_model_updater(self):
        """Background thread that periodically updates the models"""
        while self.running:
            # Sleep for designated interval
            time.sleep(self.model_update_interval)
            
            # Update the models
            self.update_models()
    
    def start(self):
        """Start the monitoring and control system"""
        self.running = True
        self.connection_active = True  # Initially connected
        
        # Start the model updater thread
        updater_thread = threading.Thread(target=self.background_model_updater)
        updater_thread.daemon = True
        updater_thread.start()
        
        self.log_event("Battery Management AI system started")
        
        try:
            last_soh_update = time.time()
            
            while self.running:
                # Read sensors
                reading = self.read_sensors()
                if not reading:
                    time.sleep(1)
                    continue
                
                # Get current timestamp
                timestamp = datetime.datetime.now()
                
                # Check safety rules
                safe_connection = self.apply_safety_rules(reading)
                
                # Get anomaly score
                anomaly_score, is_anomaly = self.detect_anomalies(reading)
                
                # Update SOH every hour
                if time.time() - last_soh_update > 3600:
                    self.soh_estimation = self.estimate_soh()
                    last_soh_update = time.time()
                
                # Store the data
                new_row = pd.DataFrame({
                    'timestamp': [timestamp],
                    'voltage': [reading['voltage']],
                    'current': [reading['current']],
                    'temperature': [reading['temperature']],
                    'soh': [self.soh_estimation],
                    'anomaly_score': [anomaly_score]
                })
                
                self.readings = pd.concat([self.readings, new_row])
                
                # Keep only the latest history_size readings
                if len(self.readings) > self.history_size:
                    self.readings = self.readings.tail(self.history_size)
                
                # Take action based on safety rules and anomaly detection
                should_connect = safe_connection and not is_anomaly
                
                # If there's a change in connection state, update the relay
                if should_connect != self.connection_active:
                    self.control_relay(should_connect)
                    
                    if is_anomaly and not safe_connection:
                        self.log_event(f"Connection severed: SAFETY RULE VIOLATION and ANOMALY DETECTED")
                    elif is_anomaly:
                        self.log_event(f"Connection severed: ANOMALY DETECTED (score: {anomaly_score:.4f})")
                    elif not safe_connection:
                        self.log_event(f"Connection severed: SAFETY RULE VIOLATION")
                
                # Wait until next sample time
                time.sleep(self.sample_rate)
                
        except KeyboardInterrupt:
            self.log_event("System stopped by user")
        except Exception as e:
            self.log_event(f"System error: {str(e)}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the monitoring system and clean up"""
        self.running = False
        self.save_models()
        GPIO.cleanup()
        self.log_event("Battery Management AI system stopped")

# Example usage
if __name__ == "__main__":
    # Set up your safety limits
    VOLTAGE_RED_LIMIT = 14.5    # Volts
    VOLTAGE_YELLOW_LIMIT = 14.0  # Volts
    CURRENT_RED_LIMIT = 3.0     # Amps
    CURRENT_YELLOW_LIMIT = 2.5   # Amps
    TEMP_RED_LIMIT = 60.0       # Celsius
    TEMP_YELLOW_LIMIT = 50.0     # Celsius
    
    # GPIO pin configuration 
    RELAY_PIN = 17  # Control pin for relay
    
    # ADC pin configuration (replace with your actual pins)
    VOLTAGE_PIN = 0  # ADC channel for voltage sensor
    CURRENT_PIN = 1  # ADC channel for current (LEM) sensor
    TEMP_PIN = 2     # ADC channel for temperature sensor
    
    # Create and start the system
    ai_system = BatteryManagementAI(
        relay_pin=RELAY_PIN,
        voltage_pin=VOLTAGE_PIN,
        current_pin=CURRENT_PIN,
        temp_pin=TEMP_PIN,
        voltage_red_limit=VOLTAGE_RED_LIMIT,
        voltage_yellow_limit=VOLTAGE_YELLOW_LIMIT,
        current_red_limit=CURRENT_RED_LIMIT,
        current_yellow_limit=CURRENT_YELLOW_LIMIT,
        temp_red_limit=TEMP_RED_LIMIT,
        temp_yellow_limit=TEMP_YELLOW_LIMIT,
        sample_rate=0.5,  # Sample every 500ms
        history_size=10000,  # Keep last 10000 readings in memory
        model_update_interval=3600  # Update model every hour
    )
    
    ai_system.start()