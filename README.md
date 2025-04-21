![logo](static/favicon.png)



# SL Timer System

A timing system designed to work with [SportLevel betting service](https://sportlevel.com/) initialy designed for drone racing, but can be modified to anything.

A Raspberry Pi-based timing system for drone racing competitions that captures start and finish events and sends them to a central server. Features a web interface for configuration and monitoring.

## Overview

The SL Timer system uses sensors connected to a Raspberry Pi to detect when drones cross the start and finish lines. Time data is precisely synchronized using NTP servers and sent to either a proxy server or directly to the SportLevel API.

### Features

- Accurate timing using NTP synchronization
- Web-based configuration and monitoring interface
- Local match history storage
- Support for both direct API and proxy server communication
- Configurable track side (red or blue)
- Real-time log viewing

## Installation

### 1. Python Setup

Ensure Python 3 is installed on your Raspberry Pi:

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

### 2. Install the Application

```bash
# Clone the repository
git clone https://github.com/Drewnja/SLDroneTimer.git
cd SLDroneTimer

# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Setup Auto-start on Boot

Create a systemd service to run the application on startup:

```bash
sudo nano /etc/systemd/system/dronetimer.service
```

Add the following content (adjust paths as needed):

```
[Unit]
Description=SL Drone Timer
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/SLDroneTimer
ExecStart=/home/pi/SLDroneTimer/venv/bin/python /home/pi/SLDroneTimer/main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl enable dronetimer.service
sudo systemctl start dronetimer.service
```

Check the status:

```bash
sudo systemctl status dronetimer.service
```

## Configuration

The system is configured using a `config.json` file. An example file (`example-config.json`) is provided as a template. Copy this file to `config.json` and modify it with your specific settings.

### Configuration Options

```json
{
    "direct_mode": false,
    "side": 1,
    "ntp_servers": [...],
    "proxy": {
        "host": "proxy-server-ip",
        "port": 1337,
        "path": "/proxy"
    },
    "direct": {
        "url": "https://your-api-endpoint.com/api/path",
        "station_code": "your_station_code",
        "secure_key": "your_secure_key_here"
    }
}
```

#### General Settings

- `direct_mode`: When `false`, the system sends data through the proxy server. When `true`, it sends directly to the configured API endpoint.
- `side`: Track side identifier - `1` for RED TRACK, `2` for BLUE TRACK.

#### NTP Server Configuration

- `ntp_servers`: An array of NTP servers to use for time synchronization. The system tries each server in sequence until it finds one that responds.

#### Proxy Mode Settings

- `proxy.host`: IP address or hostname of the proxy server
- `proxy.port`: Port number the proxy server is listening on
- `proxy.path`: API endpoint path on the proxy server

#### Direct Mode Settings

- `direct.url`: Complete URL of the direct API endpoint
- `direct.station_code`: Station identification code for the API
- `direct.secure_key`: Security key for API authentication

## Setup & Usage

1. Clone this repository
2. Copy `example-config.json` to `config.json` and update with your settings
3. Connect sensors to the appropriate GPIO pins as defined in the code
4. Run `python main.py` to start the system
5. Access the web interface at `http://<raspberry-pi-ip>:8080`

## Web Interface

The web interface provides:

- System status monitoring
- NTP synchronization
- Configuration management
- Live log viewing
- Match history and detailed timing information

## Hardware Requirements

- Raspberry Pi (3 or newer recommended)
- Start sensor (optical) connected to GPIO
- Finish sensor (vibration) connected to GPIO
- Network connectivity for time synchronization and data transmission

### GPIO Connection Instructions

Connect your hardware components to the Raspberry Pi as follows:

- Connect your start optical sensor between GPIO17 and GND
- Connect your finish vibration sensor between GPIO27 and GND
- Connect LEDs with appropriate resistors to GPIO22, GPIO23, and GPIO24
- **(Optional) Connect SC7A20H Accelerometer:**
    - Connect VCC to a 3.3V pin.
    - Connect GND to a GND pin.
    - Connect SCL to GPIO 3 (Pin 5).
    - Connect SDA to GPIO 2 (Pin 3).

![GPIO Pinout](https://www.raspberrypi.com/documentation/computers/images/GPIO-Pinout-Diagram-2.png)

### Finish Sensor Configuration

The system supports two types of finish sensors working simultaneously:
1.  **Vibration Sensor (GPIO):** Connected to `FINISH_VIBRO_PIN` (default GPIO27).
2.  **SC7A20H Accelerometer (I2C):** An optional I2C accelerometer for more sensitive landing detection.

#### SC7A20H Configuration (`config.json`)

If using the SC7A20H, configure it in `config.json`:

```json
"sc7a20h": {
    "enabled": true,         // Set to true to enable the sensor
    "i2c_bus": 1,            // I2C bus number (usually 1 on RPi)
    "noise_threshold": 0.0,  // Automatically set by calibration (leave as 0.0 initially)
    "deadzone_percent": 0    // Optional deadzone (0-100), 0 = disabled
}
```

- The system automatically attempts to detect the SC7A20H at the standard I2C address (0x19) on the specified bus during startup.
- The `noise_threshold` is critical for accurate detection and **must be set via the calibration process** in the web UI.
- The `deadzone_percent` adds a percentage buffer on top of the calibrated noise threshold. A value of 10 means the trigger level will be 110% of the calibrated threshold. It's disabled (0) by default.

#### SC7A20H Calibration (Web UI)

1.  Navigate to the **Sensors** tab in the web UI.
2.  Ensure the sensor status shows "Initialized OK".
3.  Place the sensor (and the landing platform it's attached to) on a stable surface where it will not be disturbed.
4.  Click the **"Start 10-Second Calibration"** button.
5.  **DO NOT MOVE** the sensor during the 10-second calibration period.
6.  The system will measure the background vibration/noise and calculate the maximum acceleration magnitude during this period.
7.  The `noise_threshold` will be automatically set to slightly above the measured maximum noise (110% of max noise).
8.  The new threshold is automatically saved to `config.json`.
9.  You can adjust the `Deadzone Percentage` if needed and click "Save Deadzone".

## Security Note

The `config.json` file contains sensitive information like API keys and is excluded from git by `.gitignore`. Never commit your actual configuration to a public repository. 

## Local Log Server Integration

The system can be configured to send event data (takeoff and landing) to a local HTTP server for additional logging or processing.

### Configuration

Add the following section to your `config.json`:

```json
"log_server": {
    "host": "your-log-server-ip",
    "port": 8000
}
```

- `host`: The IP address or hostname of your local log server.
- `port`: The port number your log server is listening on.

If the `log_server` section is not present or the `host`/`port` are empty, this feature will be disabled.

### Data Transmission

After each `take_off` or `landing` event is processed (regardless of whether the primary request to the proxy/direct server was successful), the SL Timer will send a `POST` request to your configured log server.

- **Endpoint**: 
    - If `side` is `1` (RED TRACK): `http://{host}:{port}/send1`
    - If `side` is `2` (BLUE TRACK): `http://{host}:{port}/send2`
- **Method**: `POST`
- **Content-Type**: `application/json`
- **Body**: A JSON object containing:
    - `type`: The event type (`"take_off"` or `"landing"`).
    - `timestamp`: The Unix timestamp (float, with millisecond precision) of the event.

### Example Request Body

```json
{
    "type": "take_off",
    "timestamp": 1678886461.123
}
```

```json
{
    "type": "landing",
    "timestamp": 1678886522.456
}
```

### Expected Server Response

The SL Timer expects an HTTP `200 OK` response from the log server upon successful receipt of the data. Other status codes will be logged as warnings. 
