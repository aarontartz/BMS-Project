import dash
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import pandas as pd
import numpy as np
import threading
import time
from datetime import datetime, timedelta
import os
import RPi.GPIO as GPIO
import sys

# Import the BatteryManagementAI class from the previous script
# Ensure this path points to where you saved the AI model script
sys.path.append('/home/pi/battery_management/')
from battery_management_ai import BatteryManagementAI

# Set up global variables
REFRESH_RATE = 1  # UI refresh rate in seconds
LOG_DIRECTORY = "/home/pi/battery_logs/"

# GPIO pin configuration 
RELAY_PIN = 17  # Control pin for relay
MANUAL_SWITCH_PIN = 27  # Physical button for manual disconnect (optional)

# ADC pin configuration
VOLTAGE_PIN = 0  # ADC channel for voltage sensor
CURRENT_PIN = 1  # ADC channel for current (LEM) sensor
TEMP_PIN = 2     # ADC channel for temperature sensor

# Safety limits
VOLTAGE_RED_LIMIT = 14.5       # Volts
VOLTAGE_YELLOW_LIMIT = 14.0    # Volts
CURRENT_RED_LIMIT = 3.0        # Amps
CURRENT_YELLOW_LIMIT = 2.5     # Amps
TEMP_RED_LIMIT = 60.0          # Celsius
TEMP_YELLOW_LIMIT = 50.0       # Celsius

# Create and start the AI system in a separate thread
battery_ai = BatteryManagementAI(
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

# Start the AI in a separate thread
ai_thread = threading.Thread(target=battery_ai.start)
ai_thread.daemon = True
ai_thread.start()

# Set up the Dash app with Bootstrap styling
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])

# Define the layout of the dashboard
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1("Battery Management System", className="text-center my-4"),
            html.Div(id="connection-status", className="text-center mb-4"),
        ], width=12)
    ]),
    
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Current Readings", className="text-center"),
                dbc.CardBody([
                    html.Div(id="live-readings", className="text-center"),
                    html.Div(id="last-updated", className="text-center text-muted mt-2"),
                ])
            ], className="mb-4")
        ], width=12)
    ]),
    
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Manual Control", className="text-center"),
                dbc.CardBody([
                    html.Div([
                        dbc.Button(
                            "EMERGENCY DISCONNECT", 
                            id="disconnect-button", 
                            color="danger", 
                            className="me-2 btn-lg",
                            style={"width": "100%", "height": "60px"}
                        ),
                    ], className="d-grid gap-2"),
                    html.Div([
                        dbc.Button(
                            "Reconnect", 
                            id="reconnect-button", 
                            color="success", 
                            className="mt-3",
                            style={"width": "100%"}
                        ),
                    ], className="d-grid gap-2 mt-2"),
                ])
            ], className="mb-4")
        ], width=12)
    ]),
    
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Battery Health", className="text-center"),
                dbc.CardBody([
                    dcc.Graph(id="soh-gauge")
                ])
            ], className="mb-4")
        ], width=6),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Anomaly Score", className="text-center"),
                dbc.CardBody([
                    dcc.Graph(id="anomaly-gauge")
                ])
            ], className="mb-4")
        ], width=6)
    ]),
    
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Historical Data", className="text-center"),
                dbc.CardBody([
                    dcc.Tabs([
                        dcc.Tab(label="Voltage", children=[
                            dcc.Graph(id="voltage-graph")
                        ]),
                        dcc.Tab(label="Current", children=[
                            dcc.Graph(id="current-graph")
                        ]),
                        dcc.Tab(label="Temperature", children=[
                            dcc.Graph(id="temperature-graph")
                        ]),
                    ])
                ])
            ], className="mb-4")
        ], width=12)
    ]),
    
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("System Logs", className="text-center"),
                dbc.CardBody([
                    html.Div(id="log-display", style={"maxHeight": "200px", "overflow": "auto"}),
                ])
            ], className="mb-4")
        ], width=12)
    ]),
    
    # Hidden div for storing data
    dcc.Store(id="data-store"),
    
    # Interval component for refreshing data
    dcc.Interval(
        id='interval-component',
        interval=REFRESH_RATE * 1000,  # in milliseconds
        n_intervals=0
    )
], fluid=True)

# Callback to update data store
@callback(
    Output("data-store", "data"),
    Input("interval-component", "n_intervals")
)
def update_data_store(n):
    """Update the central data store with latest readings"""
    if not hasattr(battery_ai, "readings") or battery_ai.readings.empty:
        return {
            "voltage": 0,
            "current": 0,
            "temperature": 0,
            "soh": 0,
            "anomaly_score": 0,
            "connection_active": False,
            "history": {
                "timestamps": [],
                "voltage": [],
                "current": [],
                "temperature": [],
                "soh": [],
                "anomaly_score": []
            },
            "logs": []
        }
    
    # Get the latest readings
    latest = battery_ai.readings.iloc[-1]
    
    # Get recent history (last 100 readings or less)
    history_size = min(100, len(battery_ai.readings))
    history_data = battery_ai.readings.tail(history_size)
    
    # Format timestamps for display
    timestamps = [ts.strftime("%H:%M:%S") for ts in history_data['timestamp']]
    
    # Get the most recent logs
    today = datetime.now().strftime('%Y%m%d')
    log_file = os.path.join(LOG_DIRECTORY, f"battery_log_{today}.txt")
    logs = []
    
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            # Get the last 20 log lines
            logs = f.readlines()[-20:]
    
    return {
        "voltage": latest['voltage'],
        "current": latest['current'],
        "temperature": latest['temperature'],
        "soh": latest['soh'],
        "anomaly_score": latest['anomaly_score'],
        "connection_active": battery_ai.connection_active,
        "history": {
            "timestamps": timestamps,
            "voltage": history_data['voltage'].tolist(),
            "current": history_data['current'].tolist(),
            "temperature": history_data['temperature'].tolist(),
            "soh": history_data['soh'].tolist(),
            "anomaly_score": history_data['anomaly_score'].tolist()
        },
        "logs": logs
    }

# Callback to update connection status
@callback(
    Output("connection-status", "children"),
    Output("connection-status", "className"),
    Input("data-store", "data")
)
def update_connection_status(data):
    """Update the connection status display"""
    if data["connection_active"]:
        return html.H3("CONNECTED", className="text-success"), "text-center mb-4"
    else:
        return html.H3("DISCONNECTED", className="text-danger"), "text-center mb-4"

# Callback to update current readings
@callback(
    Output("live-readings", "children"),
    Output("last-updated", "children"),
    Input("data-store", "data")
)
def update_live_readings(data):
    """Update the display of current sensor readings"""
    now = datetime.now().strftime("%H:%M:%S")
    
    voltage_class = "text-success"
    if data["voltage"] > VOLTAGE_YELLOW_LIMIT:
        voltage_class = "text-warning"
    if data["voltage"] > VOLTAGE_RED_LIMIT:
        voltage_class = "text-danger"
        
    current_class = "text-success"
    if data["current"] > CURRENT_YELLOW_LIMIT:
        current_class = "text-warning"
    if data["current"] > CURRENT_RED_LIMIT:
        current_class = "text-danger"
        
    temp_class = "text-success"
    if data["temperature"] > TEMP_YELLOW_LIMIT:
        temp_class = "text-warning"
    if data["temperature"] > TEMP_RED_LIMIT:
        temp_class = "text-danger"
    
    readings = dbc.Row([
        dbc.Col([
            html.H3("Voltage", className="mb-0"),
            html.H2(f"{data['voltage']:.2f} V", className=voltage_class)
        ], width=4),
        dbc.Col([
            html.H3("Current", className="mb-0"),
            html.H2(f"{data['current']:.2f} A", className=current_class)
        ], width=4),
        dbc.Col([
            html.H3("Temperature", className="mb-0"),
            html.H2(f"{data['temperature']:.1f} °C", className=temp_class)
        ], width=4)
    ])
    
    return readings, f"Last updated: {now}"

# Callback to update SoH gauge
@callback(
    Output("soh-gauge", "figure"),
    Input("data-store", "data")
)
def update_soh_gauge(data):
    """Update the State of Health gauge"""
    soh_value = data["soh"]
    
    # Define colors for different SoH ranges
    if soh_value > 80:
        color = "green"
    elif soh_value > 50:
        color = "yellow"
    else:
        color = "red"
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=soh_value,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "State of Health"},
        gauge={
            'axis': {'range': [0, 100]},
            'bar': {'color': color},
            'steps': [
                {'range': [0, 50], 'color': "lightgray"},
                {'range': [50, 80], 'color': "gray"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 50
            }
        }
    ))
    
    fig.update_layout(height=250, margin=dict(l=20, r=20, t=30, b=20))
    
    return fig

# Callback to update anomaly gauge
@callback(
    Output("anomaly-gauge", "figure"),
    Input("data-store", "data")
)
def update_anomaly_gauge(data):
    """Update the anomaly score gauge"""
    anomaly_value = data["anomaly_score"] * 100  # Convert to percentage
    
    # Define colors for different anomaly ranges
    if anomaly_value < 40:
        color = "green"
    elif anomaly_value < 80:
        color = "yellow"
    else:
        color = "red"
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=anomaly_value,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Anomaly Detection"},
        number={'suffix': '%'},
        gauge={
            'axis': {'range': [0, 100]},
            'bar': {'color': color},
            'steps': [
                {'range': [0, 40], 'color': "lightgray"},
                {'range': [40, 80], 'color': "gray"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 80
            }
        }
    ))
    
    fig.update_layout(height=250, margin=dict(l=20, r=20, t=30, b=20))
    
    return fig

# Callback to update voltage graph
@callback(
    Output("voltage-graph", "figure"),
    Input("data-store", "data")
)
def update_voltage_graph(data):
    """Update the voltage history graph"""
    fig = go.Figure()
    
    # Add voltage line
    fig.add_trace(go.Scatter(
        x=data["history"]["timestamps"],
        y=data["history"]["voltage"],
        mode='lines',
        name='Voltage',
        line=dict(color='blue', width=2)
    ))
    
    # Add horizontal lines for limits
    fig.add_shape(
        type="line",
        x0=0,
        y0=VOLTAGE_YELLOW_LIMIT,
        x1=1,
        y1=VOLTAGE_YELLOW_LIMIT,
        line=dict(color="orange", width=2, dash="dash"),
        xref="paper"
    )
    
    fig.add_shape(
        type="line",
        x0=0,
        y0=VOLTAGE_RED_LIMIT,
        x1=1,
        y1=VOLTAGE_RED_LIMIT,
        line=dict(color="red", width=2, dash="dash"),
        xref="paper"
    )
    
    # Update layout
    fig.update_layout(
        title="Voltage History",
        xaxis_title="Time",
        yaxis_title="Voltage (V)",
        height=300,
        margin=dict(l=40, r=20, t=50, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig

# Callback to update current graph
@callback(
    Output("current-graph", "figure"),
    Input("data-store", "data")
)
def update_current_graph(data):
    """Update the current history graph"""
    fig = go.Figure()
    
    # Add current line
    fig.add_trace(go.Scatter(
        x=data["history"]["timestamps"],
        y=data["history"]["current"],
        mode='lines',
        name='Current',
        line=dict(color='green', width=2)
    ))
    
    # Add horizontal lines for limits
    fig.add_shape(
        type="line",
        x0=0,
        y0=CURRENT_YELLOW_LIMIT,
        x1=1,
        y1=CURRENT_YELLOW_LIMIT,
        line=dict(color="orange", width=2, dash="dash"),
        xref="paper"
    )
    
    fig.add_shape(
        type="line",
        x0=0,
        y0=CURRENT_RED_LIMIT,
        x1=1,
        y1=CURRENT_RED_LIMIT,
        line=dict(color="red", width=2, dash="dash"),
        xref="paper"
    )
    
    # Update layout
    fig.update_layout(
        title="Current History",
        xaxis_title="Time",
        yaxis_title="Current (A)",
        height=300,
        margin=dict(l=40, r=20, t=50, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig

# Callback to update temperature graph
@callback(
    Output("temperature-graph", "figure"),
    Input("data-store", "data")
)
def update_temperature_graph(data):
    """Update the temperature history graph"""
    fig = go.Figure()
    
    # Add temperature line
    fig.add_trace(go.Scatter(
        x=data["history"]["timestamps"],
        y=data["history"]["temperature"],
        mode='lines',
        name='Temperature',
        line=dict(color='red', width=2)
    ))
    
    # Add horizontal lines for limits
    fig.add_shape(
        type="line",
        x0=0,
        y0=TEMP_YELLOW_LIMIT,
        x1=1,
        y1=TEMP_YELLOW_LIMIT,
        line=dict(color="orange", width=2, dash="dash"),
        xref="paper"
    )
    
    fig.add_shape(
        type="line",
        x0=0,
        y0=TEMP_RED_LIMIT,
        x1=1,
        y1=TEMP_RED_LIMIT,
        line=dict(color="red", width=2, dash="dash"),
        xref="paper"
    )
    
    # Update layout
    fig.update_layout(
        title="Temperature History",
        xaxis_title="Time",
        yaxis_title="Temperature (°C)",
        height=300,
        margin=dict(l=40, r=20, t=50, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig

# Callback to update logs
@callback(
    Output("log-display", "children"),
    Input("data-store", "data")
)
def update_logs(data):
    """Update the log display"""
    logs = data["logs"]
    
    if not logs:
        return html.P("No logs available")
    
    log_items = []
    for log in logs:
        # Parse log for potential coloring
        if "ERROR" in log or "RED LIMIT" in log:
            log_items.append(html.P(log, className="text-danger mb-1"))
        elif "WARNING" in log or "YELLOW LIMIT" in log:
            log_items.append(html.P(log, className="text-warning mb-1"))
        else:
            log_items.append(html.P(log, className="mb-1"))
    
    return log_items

# Callback for the manual disconnect button
@callback(
    Output("disconnect-button", "disabled"),
    Output("reconnect-button", "disabled"),
    Input("disconnect-button", "n_clicks"),
    Input("reconnect-button", "n_clicks"),
    Input("data-store", "data"),
    prevent_initial_call=True
)
def handle_manual_control(disconnect_clicks, reconnect_clicks, data):
    """Handle manual control button clicks"""
    ctx = dash.callback_context
    
    if not ctx.triggered:
        # Initial load - button states depend on connection status
        return not data["connection_active"], data["connection_active"]
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if button_id == "disconnect-button":
        if disconnect_clicks:
            battery_ai.control_relay(False)
            battery_ai.log_event("Manual disconnect initiated by user")
            return True, False
    
    elif button_id == "reconnect-button":
        if reconnect_clicks:
            battery_ai.control_relay(True)
            battery_ai.log_event("Manual reconnect initiated by user")
            return False, True
    
    # If data update triggered this callback
    return not data["connection_active"], data["connection_active"]

# For manual physical button support (optional)
def setup_manual_switch():
    """Set up the physical manual disconnect button"""
    if MANUAL_SWITCH_PIN is not None:
        GPIO.setup(MANUAL_SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(MANUAL_SWITCH_PIN, GPIO.FALLING, 
                             callback=manual_button_pressed, bouncetime=300)

def manual_button_pressed(channel):
    """Callback for physical button press"""
    battery_ai.control_relay(False)
    battery_ai.log_event("Manual disconnect initiated by physical button")

# Main function to run the server
if __name__ == '__main__':
    try:
        # Set up physical button if needed
        setup_manual_switch()
        
        # Run the Dash app
        app.run_server(debug=False, host='0.0.0.0', port=8050)
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        # Clean up
        battery_ai.stop()
        GPIO.cleanup()