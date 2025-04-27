#!/usr/bin/env python3
import time
import json
import socket
import requests
import RPi.GPIO as GPIO
import ntplib
from datetime import datetime
import sys
import select
import threading
import logging
import os

# Import web server module
import web_server

# Configuration file path
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

# Default configuration
DEFAULT_CONFIG = {
    "direct_mode": False,
    "side": 1,  # Default to RED TRACK
    "auth": {
        "username": "admin",
        "password": "admin"
    },
    "log_server": {
        "host": "localhost",
        "port": 8000
    },
    "ntp_servers": [
        "pool.ntp.org",
        "time.google.com",
        "time.windows.com",
        "time.apple.com",
        "time.cloudflare.com", 
        "time.nist.gov",
        "europe.pool.ntp.org",
        "asia.pool.ntp.org",
        "north-america.pool.ntp.org"
    ],
    "proxy": {
        "host": "192.168.1.165",
        "port": 1337,
        "path": "/proxy"
    },
    "direct": {
        "url": "https://example.com/api/v1/drone_racing/sensor/action",
        "station_code": "station_1",
        "secure_key": "key"
    }
}

# Load configuration from file
def load_config():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return config
        else:
            return DEFAULT_CONFIG.copy()
    except Exception as e:
        logging.error(f"Failed to load configuration: {e}")
        return DEFAULT_CONFIG.copy()

# Configuration
DEBUG_MODE = True  # Set to True to allow keyboard input (S/F) to trigger events
config = load_config()
DIRECT_MODE = config.get("direct_mode", False)  # Load from config file or use default

# Load NTP servers from config or use defaults
NTP_SERVERS = config.get("ntp_servers", [
    "pool.ntp.org",
    "time.google.com",
    "time.windows.com",
    "time.apple.com",
    "time.cloudflare.com",
    "time.nist.gov",
    "europe.pool.ntp.org",
    "asia.pool.ntp.org",
    "north-america.pool.ntp.org"
])

# Track side - load from config (1 for RED TRACK, 2 for BLUE TRACK)
SIDE = config.get("side", 1)

# Proxy server settings - load from config
proxy_config = config.get("proxy", DEFAULT_CONFIG["proxy"])
SERVER_HOST = proxy_config.get("host", DEFAULT_CONFIG["proxy"]["host"])
SERVER_PORT = proxy_config.get("port", DEFAULT_CONFIG["proxy"]["port"])
SERVER_PATH = proxy_config.get("path", DEFAULT_CONFIG["proxy"]["path"])

# Direct server settings - load from config
direct_config = config.get("direct", DEFAULT_CONFIG["direct"])
DIRECT_SERVER_URL = direct_config.get("url", DEFAULT_CONFIG["direct"]["url"])
STATION_CODE = direct_config.get("station_code", DEFAULT_CONFIG["direct"]["station_code"])
SECURE_KEY = direct_config.get("secure_key", DEFAULT_CONFIG["direct"]["secure_key"])

# Log server settings
log_server_config = config.get("log_server", DEFAULT_CONFIG["log_server"])
LOG_SERVER_HOST = log_server_config.get("host", DEFAULT_CONFIG["log_server"]["host"])
LOG_SERVER_PORT = log_server_config.get("port", DEFAULT_CONFIG["log_server"]["port"])

# Pin definitions (BCM mode)
START_OPT_PIN = 17  # Adjust as needed for your RPi connections
FINISH_VIBRO_PIN = 27  # Adjust as needed for your RPi connections
LED_START_PIN = 22  # Adjust as needed for your RPi connections
LED_FINISH_PIN = 23  # Adjust as needed for your RPi connections
LED_FINISH2_PIN = 24  # Adjust as needed for your RPi connections

# Timing constants
START_DELAY = 2.0  # 2 seconds delay
REQUEST_TIMEOUT = 0.5  # 500ms timeout

# Configure logging
logger = logging.getLogger(__name__)

# Global state variables
ff = False
start_activated = False
start_sensor_active_time = 0
current_match = {
    "start_time": None,
    "start_log": None,
    "start_response": None,
    "in_progress": False
}

class SensorSystem:
    """Main sensor system class that encapsulates all functionality"""
    
    def __init__(self):
        # Load configuration first
        self.config = load_config()
        
        # Reference class attributes to module constants/config for web server access
        self.DEBUG_MODE = DEBUG_MODE
        self.DIRECT_MODE = self.config.get("direct_mode", DEFAULT_CONFIG["direct_mode"])
        self.SIDE = self.config.get("side", DEFAULT_CONFIG["side"])
        self.NTP_SERVERS = self.config.get("ntp_servers", DEFAULT_CONFIG["ntp_servers"])
        
        # Proxy settings
        proxy_config = self.config.get("proxy", DEFAULT_CONFIG["proxy"])
        self.SERVER_HOST = proxy_config.get("host", DEFAULT_CONFIG["proxy"]["host"])
        self.SERVER_PORT = proxy_config.get("port", DEFAULT_CONFIG["proxy"]["port"])
        self.SERVER_PATH = proxy_config.get("path", DEFAULT_CONFIG["proxy"]["path"])
        
        # Direct settings
        direct_config = self.config.get("direct", DEFAULT_CONFIG["direct"])
        self.DIRECT_SERVER_URL = direct_config.get("url", DEFAULT_CONFIG["direct"]["url"])
        self.STATION_CODE = direct_config.get("station_code", DEFAULT_CONFIG["direct"]["station_code"])
        self.SECURE_KEY = direct_config.get("secure_key", DEFAULT_CONFIG["direct"]["secure_key"])

        # Log server settings
        log_server_config = self.config.get("log_server", DEFAULT_CONFIG["log_server"])
        self.LOG_SERVER_HOST = log_server_config.get("host", DEFAULT_CONFIG["log_server"]["host"])
        self.LOG_SERVER_PORT = log_server_config.get("port", DEFAULT_CONFIG["log_server"]["port"])
        
        # State variables
        self.ff = False
        self.start_activated = False
        self.start_sensor_active_time = 0
        self.current_match = {
            "start_time": None,
            "start_log": None,
            "start_response": None,
            "in_progress": False
        }
        
        # Initialize the system
        self.setup()
        
        # Start web server
        self.start_web_server()
    
    def try_ntp_sync(self):
        """Try to synchronize with NTP servers, trying each in sequence"""
        ntp_client = ntplib.NTPClient()
        
        for server in self.NTP_SERVERS:
            try:
                logger.info(f"Trying NTP server: {server}")
                ntp_response = ntp_client.request(server, version=3, timeout=2)
                if ntp_response.tx_time > 1000000000:  # After year ~2001
                    logger.info(f"Successfully synchronized time with {server}")
                    # Add server name to the response object
                    ntp_response.server = server
                    
                    # Update the last sync info in web_server module for display
                    import web_server
                    web_server.last_ntp_sync_time = datetime.fromtimestamp(ntp_response.tx_time).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    web_server.last_ntp_sync_server = server
                    
                    return ntp_response
                else:
                    logger.warning(f"Invalid time received from {server}")
            except Exception as e:
                logger.warning(f"Failed to sync with {server}: {e}")
        
        raise Exception("Failed to synchronize with any NTP server")

    def setup(self):
        """Initialize GPIO, network, and NTP"""
        logger.info("=== Starting Sensor System ===")
        
        # Initialize GPIO
        logger.info("Initializing pins...")
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Setup pins
        GPIO.setup(START_OPT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Pulled up, active low
        GPIO.setup(FINISH_VIBRO_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Pulled up, active low
        GPIO.setup(LED_START_PIN, GPIO.OUT)
        GPIO.setup(LED_FINISH_PIN, GPIO.OUT)
        GPIO.setup(LED_FINISH2_PIN, GPIO.OUT)
        logger.info("Pins initialized")
        
        # Initialize all LEDs to OFF
        GPIO.output(LED_START_PIN, GPIO.LOW)
        GPIO.output(LED_FINISH_PIN, GPIO.LOW)
        GPIO.output(LED_FINISH2_PIN, GPIO.LOW)
        
        if DEBUG_MODE:
            logger.info("=== DEBUG MODE ACTIVE ===")
            logger.info("Press 'S' to simulate START sensor")
            logger.info("Press 'F' to simulate FINISH sensor")
            logger.info("Press 'Q' to quit")
        
        # Test connectivity, but don't exit on failure
        connection_success = True
        # If not using direct mode, test proxy server connectivity
        if not self.DIRECT_MODE:
            # Test network connectivity
            logger.info("Testing network connectivity to proxy server...")
            try:
                socket.create_connection((self.SERVER_HOST, self.SERVER_PORT), timeout=5)
                logger.info("Successfully connected to proxy server!")
                self.blink_start_led(3, 0.3)  # Blink 3 times to indicate success
            except Exception as e:
                logger.error(f"Failed to connect to proxy server! Error: {e}")
                logger.error("Please check:")
                logger.error("1. Network connection")
                logger.error("2. IP address configuration")
                logger.error("3. Gateway and DNS settings")
                logger.error("4. Proxy server is running")
                logger.warning("Will continue running, but server connection is not available at the moment.")
                self.blink_start_led(5, 0.2)  # Blink 5 times to indicate error
                connection_success = False
        else:
            logger.info("=== DIRECT MODE ACTIVE ===")
            logger.info(f"Sending requests directly to: {self.DIRECT_SERVER_URL}")
            logger.info("Testing direct server connectivity...")
            try:
                # Use POST instead of GET and enable SSL verification
                test_data = {
                    "station_code": self.STATION_CODE,
                    "secure_key": self.SECURE_KEY,
                    "event_type": "test",
                    "event_body": {
                        "side": self.SIDE,
                        "time": time.time()
                    }
                }
                response = requests.post(
                    self.DIRECT_SERVER_URL,
                    json=test_data,
                    timeout=5
                )
                logger.info(f"Direct server response code: {response.status_code}")
                logger.info(f"Direct server response body: {response.text}")
                self.blink_start_led(3, 0.3)  # Blink 3 times to indicate success
            except Exception as e:
                logger.warning(f"Warning: Could not connect to direct server: {e}")
                logger.warning("Will still attempt to send events when triggered")
                self.blink_start_led(5, 0.2)  # Blink 5 times to indicate error
                connection_success = False
        
        # Test NTP synchronization
        ntp_success = True
        logger.info("Initializing NTP client...")
        try:
            ntp_response = self.try_ntp_sync()
            logger.info("NTP time synchronized successfully")
        except Exception as e:
            logger.error(f"Failed to synchronize NTP time! Error: {e}")
            logger.warning("System will proceed but may have less accurate timing.")
            self.error_blink_pattern(3)  # Show error but continue
            ntp_success = False
        
        # Log overall status, but never exit
        if connection_success and ntp_success:
            logger.info("=== Setup Complete Successfully ===")
        else:
            logger.warning("=== Setup Complete with Warnings ===")
            logger.warning("Some services are not available, but system will continue to function.")
    
    def get_current_time(self):
        """Get current time with millisecond precision (using system time)"""
        # Use system time directly without NTP sync
        return time.time()
    
    def error_blink_pattern(self, count):
        """Error indication - alternates all LEDs in a pattern"""
        for _ in range(count):
            # All LEDs on
            GPIO.output(LED_START_PIN, GPIO.HIGH)
            GPIO.output(LED_FINISH_PIN, GPIO.HIGH)
            GPIO.output(LED_FINISH2_PIN, GPIO.HIGH)
            time.sleep(0.3)
            
            # All LEDs off
            GPIO.output(LED_START_PIN, GPIO.LOW)
            GPIO.output(LED_FINISH_PIN, GPIO.LOW)
            GPIO.output(LED_FINISH2_PIN, GPIO.LOW)
            time.sleep(0.3)
    
    def blink_start_led(self, count, delay_sec):
        """Blink the start LED a specified number of times"""
        for _ in range(count):
            GPIO.output(LED_START_PIN, GPIO.HIGH)
            time.sleep(delay_sec)
            GPIO.output(LED_START_PIN, GPIO.LOW)
            time.sleep(delay_sec)
    
    def send_log_request(self, event_type, event_time):
        """Send event data to the local log server"""
        try:
            if not self.LOG_SERVER_HOST or not self.LOG_SERVER_PORT:
                logger.info("Log server not configured, skipping log request.")
                return

            # Determine endpoint based on side
            endpoint = f"/send{self.SIDE}"
            url = f"http://{self.LOG_SERVER_HOST}:{self.LOG_SERVER_PORT}{endpoint}"
            
            # Prepare JSON data
            log_data = {
                "type": event_type, 
                "timestamp": round(event_time, 3)
            }
            
            logger.info(f"Sending log data to {url}: {json.dumps(log_data)}")
            
            response = requests.post(url, json=log_data, timeout=2)
            
            if response.status_code == 200:
                logger.info("Log request successful.")
            else:
                logger.warning(f"Log request failed! Status: {response.status_code}, Body: {response.text}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send log request: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred while sending log request: {e}")

    def send_post_request(self, side, event_type, event_time):
        """Send POST request to the server"""
        logger.info("=== Sending POST Request ===")
        
        # Check if time is valid before sending request
        if event_time < 1000000000:
            logger.error("Invalid timestamp (before 2001)!")
            return False
        
        # NTP sync before sending request removed as requested
        
        if self.DIRECT_MODE:
            return self.send_direct_request(side, event_type, event_time)
        else:
            return self.send_proxy_request(side, event_type, event_time)
    
    def send_proxy_request(self, side, event_type, event_time):
        """Send request through proxy server"""
        # Prepare JSON data
        json_data = {
            "station_code": self.STATION_CODE,
            "secure_key": self.SECURE_KEY,
            "event_type": event_type,
            "event_body": {
                "side": side,
                "time": round(event_time, 3)
            }
        }
        
        # Multiple retry attempts
        MAX_RETRIES = 3
        for attempt in range(MAX_RETRIES):
            if attempt > 0:
                logger.info(f"Retry attempt {attempt} of {MAX_RETRIES - 1}...")
                time.sleep(1)  # Delay between retries
            
            try:
                url = f"http://{self.SERVER_HOST}:{self.SERVER_PORT}{self.SERVER_PATH}"
                logger.info("Connecting to proxy server...")
                logger.info(f"Sending data: {json.dumps(json_data)}")
                
                response = requests.post(
                    url,
                    json=json_data,
                    timeout=5  # 5 seconds timeout
                )
                
                logger.info(f"Response Status: {response.status_code}")
                logger.info(f"Response Body: {response.text}")
                
                # Store response for match tracking
                response_text = f"Status: {response.status_code}\nBody: {response.text}"
                self.last_response_data = response_text
                
                if response.status_code == 200:
                    logger.info("Request successful (200 OK)")
                    logger.info("=== Request Complete ===")
                    return True
                else:
                    logger.warning(f"Request failed! Non-200 response received: {response.status_code}")
                    continue  # Try the next retry
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Connection error: {e}")
                # Store error as response for match tracking
                self.last_response_data = f"Connection error: {e}"
                continue  # Try the next retry
        
        logger.error("All retry attempts failed!")
        logger.error("=== Request Failed ===")
        return False
    
    def send_direct_request(self, side, event_type, event_time):
        """Send request directly to the server"""
        logger.info("Sending direct request to external server...")
        
        # Prepare JSON data - structure depends on event type for DIRECT mode
        if event_type == "take_off":
            # Use absolute_time for take_off events in direct mode
            json_data = {
                "station_code": self.STATION_CODE,
                "secure_key": self.SECURE_KEY,
                "event_type": event_type,
                "absolute_time": round(event_time, 3)
            }
            logger.info(f"Using 'absolute_time' key for {event_type} event.")
        else:
            # Use standard event_body structure for other events (e.g., test)
            # Note: Landing events are currently skipped in direct mode for the primary request
            json_data = {
                "station_code": self.STATION_CODE,
                "secure_key": self.SECURE_KEY,
                "event_type": event_type,
                "event_body": {
                    "side": side,
                    "time": round(event_time, 3)
                }
            }
            logger.info(f"Using standard 'event_body.time' key for {event_type} event.")
        
        # Multiple retry attempts
        MAX_RETRIES = 3
        for attempt in range(MAX_RETRIES):
            if attempt > 0:
                logger.info(f"Retry attempt {attempt} of {MAX_RETRIES - 1}...")
                time.sleep(1)  # Delay between retries
            
            try:
                logger.info(f"Sending data: {json.dumps(json_data)}")
                
                response = requests.post(
                    self.DIRECT_SERVER_URL,
                    json=json_data,
                    timeout=5  # 5 seconds timeout
                )
                
                logger.info(f"Response Status: {response.status_code}")
                logger.info(f"Response Body: {response.text}")
                
                # Store response for match tracking
                response_text = f"Status: {response.status_code}\nBody: {response.text}"
                self.last_response_data = response_text
                
                if response.status_code == 200:
                    logger.info("Request successful (200 OK)")
                    logger.info("=== Request Complete ===")
                    return True
                else:
                    logger.warning(f"Request failed! Non-200 response received: {response.status_code}")
                    continue  # Try the next retry
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Connection error: {e}")
                # Store error as response for match tracking
                self.last_response_data = f"Connection error: {e}"
                continue  # Try the next retry
        
        logger.error("All retry attempts failed!")
        logger.error("=== Request Failed ===")
        return False
    
    def send_post_request_take_off(self, side, event_time):
        """Send take_off event and record match start"""
        # Capture log before sending request
        start_log = f"Starting take-off event at {datetime.fromtimestamp(event_time).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}, side: {side}"
        logger.info(start_log)
        
        # Send primary request and get result
        success = self.send_post_request(side, "take_off", event_time)
        
        # Get the response data (will be added in send_post_request)
        response_data = getattr(self, "last_response_data", "No response data")
        
        # Send log request regardless of primary request success
        self.send_log_request("take_off", event_time)
        
        # Store match start data regardless of request success
        self.current_match = {
            "start_time": event_time,
            "start_log": start_log,
            "start_response": response_data,
            "in_progress": True
        }
        
        if success:
            logger.info("Match started successfully and recorded")
        else:
            logger.warning("Match started with request errors but still recorded for database")
        
        return success
    
    def send_post_request_landing(self, side, event_time):
        """Send landing event and complete match record"""
        # Capture log before sending request
        finish_log = f"Landing event at {datetime.fromtimestamp(event_time).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}, side: {side}"
        logger.info(finish_log)
        
        # Send primary request and get result, ONLY IF NOT IN DIRECT MODE
        success = True  # Default to success if skipping primary request
        response_data = "Request skipped (Direct Mode)"
        if not self.DIRECT_MODE:
            logger.info("Sending landing event to primary server (Proxy Mode)")
            success = self.send_post_request(side, "landing", event_time)
            response_data = getattr(self, "last_response_data", "No response data")
        else:
            logger.info("Skipping landing event send to primary server (Direct Mode)")
            # Although we skip the primary request, we still need to update NTP
            try:
                ntp_response = self.try_ntp_sync()
                logger.info("NTP time updated after landing event processing (Direct Mode)")
            except Exception as e:
                logger.warning(f"Could not update NTP time after landing event (Direct Mode): {e}")
        
        # Send log request regardless of primary request success or mode
        self.send_log_request("landing", event_time)
        
        # If we have a match in progress, complete it regardless of request success
        if self.current_match["in_progress"]:
            # Complete match data
            start_time = self.current_match["start_time"]
            start_log = self.current_match["start_log"]
            start_response = self.current_match["start_response"]
            
            # Reset current match
            self.current_match = {
                "start_time": None,
                "start_log": None,
                "start_response": None,
                "in_progress": False
            }
            
            # Save match to database even if request failed
            import web_server
            web_server.save_match(
                side, 
                start_time, 
                event_time, 
                start_log, 
                finish_log, 
                start_response, 
                response_data
            )
            
            match_time = event_time - start_time
            if success:
                logger.info(f"Match completed successfully and saved: {match_time:.2f} seconds")
            else:
                logger.warning(f"Match completed with request errors but still saved to database: {match_time:.2f} seconds")
        else:
            logger.warning("Finish event received but no matching start event found")
        
        return success
    
    def check_keyboard_input(self):
        """Check for keyboard input in non-blocking mode"""
        if not self.DEBUG_MODE:
            return None
            
        if select.select([sys.stdin], [], [], 0.0)[0]:
            key = sys.stdin.read(1)
            return key.upper()
        return None
    
    def trigger_start_event(self):
        """Trigger the start event directly (used in debug mode)"""
        logger.info("DEBUG: Triggering start event immediately")
        # Use system time directly instead of get_current_time to avoid NTP sync
        event_time = time.time()
        self.send_post_request_take_off(self.SIDE, event_time)
    
    def trigger_finish_event(self):
        """Trigger the finish event directly (used in debug mode)"""
        logger.info("DEBUG: Triggering finish event immediately")
        # Use system time directly instead of get_current_time to avoid NTP sync
        event_time = time.time()
        success = self.send_post_request_landing(self.SIDE, event_time)
        
        # Force NTP update AFTER landing event is processed (same as in main loop)
        try:
            ntp_response = self.try_ntp_sync()
            logger.info("NTP time updated after landing event processing")
        except Exception as e:
            logger.warning(f"Could not update NTP time after landing event: {e}")
    
    def start_web_server(self):
        """Start the web server in a separate thread"""
        # Initialize web server with a reference to this sensor system
        web_server.initialize_web_server(self)
        
        # Start web server in a separate thread
        web_thread = threading.Thread(target=web_server.run_web_server)
        web_thread.daemon = True
        web_thread.start()
        logger.info("Web server started at http://0.0.0.0:8080")
    
    def run(self):
        """Main program loop"""
        last_start_state = True  # Pulled up, so default is True
        last_finish_state = True
        
        # Setup non-blocking keyboard input for debug mode
        has_interactive_terminal = False
        if self.DEBUG_MODE:
            import termios
            import tty
            
            # Check if running in an interactive terminal
            try:
                # Test if we can get terminal attributes - will fail if running as service
                termios.tcgetattr(sys.stdin)
                has_interactive_terminal = True
                
                # Only setup keyboard input if we have an interactive terminal
                if has_interactive_terminal:
                    old_settings = termios.tcgetattr(sys.stdin)
                    try:
                        tty.setcbreak(sys.stdin.fileno())
                        logger.info("Debug keyboard input enabled - press S for START, F for FINISH, Q to quit")
                    except Exception as e:
                        logger.warning(f"Could not set terminal to raw mode: {e}")
                        logger.warning("Debug keyboard input may not work correctly")
                        has_interactive_terminal = False
            except Exception as e:
                logger.warning(f"Running in non-interactive mode (service): {e}")
                logger.warning("Debug keyboard input disabled")
                has_interactive_terminal = False
        
        logger.info("Starting main loop...")
        
        try:
            while True:
                # Read current sensor states
                current_start_state = GPIO.input(START_OPT_PIN)
                current_finish_state = GPIO.input(FINISH_VIBRO_PIN)
                
                # Debug mode - check for keyboard input only if we have an interactive terminal
                if self.DEBUG_MODE and has_interactive_terminal:
                    key = self.check_keyboard_input()
                    if key == 'S':
                        logger.info("DEBUG: Simulating START sensor activation")
                        # In debug mode, trigger the start event immediately
                        self.trigger_start_event()
                        # Reset the sensor states to prevent additional triggers
                        current_start_state = True
                        last_start_state = True
                    elif key == 'F':
                        logger.info("DEBUG: Simulating FINISH sensor activation")
                        # In debug mode, trigger the finish event immediately
                        self.trigger_finish_event()
                        # Reset the sensor states to prevent additional triggers
                        current_finish_state = True
                        last_finish_state = True
                    elif key == 'Q':
                        logger.info("DEBUG: Quitting program")
                        break
                
                # Check start optical sensor state changes
                if current_start_state != last_start_state:
                    logger.info(f"Start sensor state changed to: {'INACTIVE' if current_start_state else 'ACTIVE'}")
                    logger.info(f"Start sensor GPIO pin {START_OPT_PIN} value: {current_start_state}")
                    
                    if not current_start_state:  # Sensor became active (pulled low)
                        self.start_sensor_active_time = time.time()
                        logger.info("Starting 2-second timer...")
                        self.start_activated = False
                    else:  # Sensor became inactive
                        if self.ff and not self.start_activated:
                            logger.info("Start sensor released before 2 seconds - ignoring")
                        elif self.ff and self.start_activated:
                            logger.info("Triggering take-off event")
                            # Use system time directly instead of get_current_time to avoid NTP sync
                            event_time = time.time()
                            self.send_post_request_take_off(self.SIDE, event_time)
                        
                        self.ff = False
                        self.start_activated = False
                    
                    last_start_state = current_start_state
                
                # Start sensor logic with 2-second delay
                if not current_start_state:  # Active Low
                    GPIO.output(LED_START_PIN, GPIO.HIGH)
                    
                    # Check if sensor has been active for 2 seconds
                    if not self.ff and not self.start_activated and (time.time() - self.start_sensor_active_time >= START_DELAY):
                        logger.info("2-second threshold reached - activating start")
                        self.ff = True
                        self.start_activated = True
                else:
                    GPIO.output(LED_START_PIN, GPIO.LOW)
                
                # Check finish sensor state changes
                if current_finish_state != last_finish_state:
                    logger.info(f"Finish sensor state changed to: {'INACTIVE' if current_finish_state else 'ACTIVE'}")
                    logger.info(f"Finish sensor GPIO pin {FINISH_VIBRO_PIN} value: {current_finish_state}")
                    logger.info(f"Start sensor state when finish changed: {'INACTIVE' if current_start_state else 'ACTIVE'}")
                    last_finish_state = current_finish_state
                
                # Finish sensor logic (active low, like start sensor)
                if not current_finish_state and current_start_state:  # Both sensors are active LOW
                    logger.info("Triggering landing event")
                    logger.info(f"Finish sensor GPIO pin {FINISH_VIBRO_PIN} value: {current_finish_state}")
                    logger.info(f"Start sensor GPIO pin {START_OPT_PIN} value: {current_start_state}")
                    
                    # Record timestamp immediately when the event is triggered
                    # Use system time directly instead of get_current_time to avoid NTP sync
                    event_time = time.time()
                    
                    GPIO.output(LED_FINISH_PIN, GPIO.HIGH)
                    GPIO.output(LED_FINISH2_PIN, GPIO.LOW)
                    
                    # NTP sync before sending request removed as requested
                    
                    success = self.send_post_request_landing(self.SIDE, event_time)
                    
                    # Force NTP update AFTER landing event is processed
                    try:
                        ntp_response = self.try_ntp_sync()
                        logger.info("NTP time updated after landing event processing")
                    except Exception as e:
                        logger.warning(f"Could not update NTP time after landing event: {e}")
                    
                    if success:
                        logger.info("Landing event successfully processed")
                        
                        # Add delay to ensure the request is complete
                        time.sleep(1)
                        
                        # Reset states for next detection
                        self.ff = False
                        self.start_activated = False
                    else:
                        logger.error("Landing event failed to process properly!")
                        # Visual error indication - blink pattern
                        self.error_blink_pattern(5)
                        
                        # Reset states for next detection
                        self.ff = False
                        self.start_activated = False
                
                elif not current_start_state:
                    GPIO.output(LED_FINISH_PIN, GPIO.LOW)
                    GPIO.output(LED_FINISH2_PIN, GPIO.HIGH)
                
                # Short sleep to reduce CPU usage
                time.sleep(0.01)
        
        except KeyboardInterrupt:
            logger.info("Program terminated by user")
        finally:
            # Restore terminal settings if in debug mode
            if self.DEBUG_MODE and has_interactive_terminal:
                try:
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                except:
                    pass
            GPIO.cleanup()
            logger.info("GPIO cleaned up")


def main():
    """Main entry point"""
    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Create and run the sensor system
    sensor_system = SensorSystem()
    sensor_system.run()


if __name__ == "__main__":
    main()
