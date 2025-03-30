# SL Timer System

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

## Security Note

The `config.json` file contains sensitive information like API keys and is excluded from git by `.gitignore`. Never commit your actual configuration to a public repository. 