#!/usr/bin/env python3
import logging
import json
import time
import queue
import os
import sqlite3
import subprocess
from datetime import datetime
from flask import Flask, render_template, jsonify, request, redirect, Response, session, url_for
import threading
from collections import deque
from functools import wraps

# Create Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)  # Generate a random secret key for sessions

# Global variables
log_queue = queue.Queue(maxsize=1000)  # Store the last 1000 log entries
log_buffer = []  # Buffer to store log entries for web display
last_ntp_sync_time = None
last_ntp_sync_server = None
sensor_system = None  # Will be set when initialized
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "matches.db")  # Absolute path to SQLite database file
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")  # Config file path

# Default configuration
DEFAULT_CONFIG = {
    "direct_mode": False,
    "auth": {
        "username": "admin",
        "password": "admin"
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
    ]
}

# Login decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle login page and authentication"""
    error = None
    config = load_config()
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if (username == config['auth']['username'] and 
            password == config['auth']['password']):
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            error = 'Invalid credentials'
    
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    """Handle logout"""
    session.pop('logged_in', None)
    return redirect(url_for('login'))

# Setup logging
class QueueHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        
        # Skip web access logs
        if ' - - [' in log_entry and ('] "GET ' in log_entry or '] "POST ' in log_entry):
            return
            
        # Skip empty logs
        if not log_entry.strip():
            return
        
        log_buffer.append(log_entry)
        if len(log_buffer) > 1000:  # Keep only the last 1000 entries
            log_buffer.pop(0)
        try:
            log_queue.put_nowait(log_entry)
        except queue.Full:
            log_queue.get()  # Remove oldest entry
            log_queue.put_nowait(log_entry)

# Configure logger
def setup_logging():
    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Add queue handler
    queue_handler = QueueHandler()
    queue_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    queue_handler.setFormatter(formatter)
    logging.getLogger().addHandler(queue_handler)
    
    return logging.getLogger(__name__)

logger = setup_logging()

def initialize_database():
    """Initialize SQLite database for storing match data"""
    try:
        logger.info(f"Initializing match database at {DB_PATH}")
        
        # Create database directory if it doesn't exist
        db_dir = os.path.dirname(DB_PATH)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"Created database directory: {db_dir}")
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Create matches table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            side INTEGER NOT NULL,
            start_time REAL NOT NULL,
            finish_time REAL NOT NULL,
            start_time_formatted TEXT NOT NULL,
            finish_time_formatted TEXT NOT NULL,
            match_time REAL NOT NULL,
            start_log TEXT,
            finish_log TEXT,
            start_response TEXT,
            finish_response TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Match database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        logger.error(f"Database path: {DB_PATH}")
        # Try to create an empty file to test permissions
        try:
            with open(DB_PATH, 'a'):
                pass
            logger.info("Successfully created empty database file")
        except Exception as write_error:
            logger.error(f"Failed to create database file: {write_error}")

def save_match(side, start_time, finish_time, start_log, finish_log, start_response, finish_response):
    """Save match data to SQLite database"""
    try:
        # Ensure database is initialized
        if not os.path.exists(DB_PATH):
            logger.warning("Database file not found, reinitializing...")
            initialize_database()
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        match_time = finish_time - start_time
        start_time_formatted = datetime.fromtimestamp(start_time).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        finish_time_formatted = datetime.fromtimestamp(finish_time).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        cursor.execute('''
        INSERT INTO matches 
        (side, start_time, finish_time, start_time_formatted, finish_time_formatted, match_time, 
         start_log, finish_log, start_response, finish_response)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            side, start_time, finish_time, start_time_formatted, finish_time_formatted, match_time,
            start_log, finish_log, start_response, finish_response
        ))
        
        # Keep only the most recent 40 matches
        cursor.execute('''
        DELETE FROM matches WHERE id NOT IN (
            SELECT id FROM matches ORDER BY created_at DESC LIMIT 40
        )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Match saved to database: {match_time:.2f} seconds")
        return True
    except Exception as e:
        logger.error(f"Failed to save match: {e}")
        # Try to create table if it doesn't exist
        try:
            initialize_database()
            logger.info("Reinitialized database after error")
        except:
            pass
        return False

def get_matches():
    """Get recent matches from the database"""
    try:
        # Check if database exists, initialize if not
        if not os.path.exists(DB_PATH):
            logger.warning("Database not found, initializing...")
            initialize_database()
            return []  # Return empty list if we just initialized
            
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='matches'")
        if not cursor.fetchone():
            logger.warning("Matches table doesn't exist, initializing database...")
            conn.close()
            initialize_database()
            return []
        
        cursor.execute('''
        SELECT * FROM matches ORDER BY created_at DESC LIMIT 40
        ''')
        
        matches = [dict(row) for row in cursor.fetchall()]
        
        # Format match time for display
        for match in matches:
            match['match_time'] = f"{match['match_time']:.2f}"
        
        conn.close()
        return matches
    except Exception as e:
        logger.error(f"Failed to get matches: {e}")
        # Try to reinitialize on error
        try:
            initialize_database()
        except:
            pass
        return []

def clear_matches():
    """Clear all matches from the database"""
    try:
        # Check if database exists
        if not os.path.exists(DB_PATH):
            logger.warning("Database not found, nothing to clear")
            return True
            
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='matches'")
        if not cursor.fetchone():
            logger.warning("Matches table doesn't exist, nothing to clear")
            conn.close()
            return True
        
        # Delete all matches
        cursor.execute('DELETE FROM matches')
        conn.commit()
        conn.close()
        
        logger.info("Match history cleared successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to clear matches: {e}")
        return False

def initialize_web_server(sensor_system_instance):
    """Initialize the web server with a reference to the sensor system"""
    global sensor_system
    sensor_system = sensor_system_instance
    
    # Load configuration and apply settings
    config = load_config()
    
    # Apply direct mode from config
    sensor_system.DIRECT_MODE = config.get("direct_mode", False)
    logger.info(f"Applied direct mode from config: {'DIRECT' if sensor_system.DIRECT_MODE else 'PROXY'}")
    
    # Apply NTP servers from config
    ntp_servers = config.get("ntp_servers", sensor_system.NTP_SERVERS)
    sensor_system.NTP_SERVERS = ntp_servers
    logger.info(f"Applied NTP servers from config: {', '.join(ntp_servers)}")
    
    # Log track side from config
    logger.info(f"Track side from config: {'RED' if sensor_system.SIDE == 1 else 'BLUE'} TRACK (side: {sensor_system.SIDE})")
    
    # Initialize the database for match storage
    initialize_database()
    
    logger.info("Web server initialized with sensor system reference")

@app.route('/')
@login_required
def index():
    """Main web interface"""
    # Get latest matches for the Matches tab
    matches = get_matches()
    
    return render_template(
        'index.html',
        logs=list(log_buffer),
        side=sensor_system.SIDE,
        direct_mode=sensor_system.DIRECT_MODE,
        debug_mode=sensor_system.DEBUG_MODE,
        current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        last_ntp_sync_time=last_ntp_sync_time,
        last_ntp_sync_server=last_ntp_sync_server,
        ntp_servers=sensor_system.NTP_SERVERS,
        matches=matches
    )

@app.route('/api/system_info')
@login_required
def system_info():
    """API endpoint to get system information"""
    return jsonify({
        'current_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'side': sensor_system.SIDE,
        'direct_mode': sensor_system.DIRECT_MODE,
        'debug_mode': sensor_system.DEBUG_MODE,
        'last_ntp_sync_time': last_ntp_sync_time,
        'last_ntp_sync_server': last_ntp_sync_server
    })

@app.route('/api/trigger_ntp_sync', methods=['POST'])
@login_required
def trigger_ntp_sync_endpoint():
    """API endpoint to trigger NTP synchronization"""
    global last_ntp_sync_time, last_ntp_sync_server
    
    try:
        ntp_response = sensor_system.try_ntp_sync()
        current_time = datetime.fromtimestamp(ntp_response.tx_time).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        last_ntp_sync_time = current_time
        last_ntp_sync_server = getattr(ntp_response, 'server', 'Unknown')
        
        logger.info(f"Manual NTP sync successful with {last_ntp_sync_server}")
        return jsonify({
            "success": True, 
            "time": current_time,
            "server": last_ntp_sync_server
        })
    except Exception as e:
        logger.error(f"Manual NTP sync failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        })

@app.route('/api/matches')
@login_required
def get_matches_endpoint():
    """API endpoint to get matches"""
    matches = get_matches()
    return jsonify(matches)

@app.route('/api/clear_matches', methods=['POST'])
@login_required
def clear_matches_endpoint():
    """API endpoint to clear all matches from the database"""
    success = clear_matches()
    if success:
        return jsonify({"success": True, "message": "Match history cleared successfully"})
    else:
        return jsonify({"success": False, "error": "Failed to clear match history"})

@app.route('/api/trigger_start')
@login_required
def trigger_start_endpoint():
    """API endpoint to trigger a start event"""
    if sensor_system.DEBUG_MODE:
        logger.info("Web interface triggered START event")
        sensor_system.trigger_start_event()
    return redirect('/')

@app.route('/api/trigger_finish')
@login_required
def trigger_finish_endpoint():
    """API endpoint to trigger a finish event"""
    if sensor_system.DEBUG_MODE:
        logger.info("Web interface triggered FINISH event")
        sensor_system.trigger_finish_event()
    return redirect('/')

@app.route('/api/export_database')
@login_required
def export_database():
    """API endpoint to download the matches database file"""
    try:
        if os.path.exists(DB_PATH):
            return Response(
                open(DB_PATH, 'rb').read(),
                mimetype='application/x-sqlite3',
                headers={
                    'Content-Disposition': 'attachment; filename=matches.db',
                    'Content-Type': 'application/x-sqlite3'
                }
            )
        else:
            return jsonify({"error": "Database file not found"}), 404
    except Exception as e:
        logger.error(f"Failed to export database: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/log_stream')
@login_required
def log_stream():
    """Server-sent event stream for logs"""
    def generate():
        last_msg = None
        while True:
            try:
                # Non-blocking queue get with timeout
                msg = log_queue.get(timeout=0.5)
                if msg != last_msg:  # Avoid duplicates
                    last_msg = msg
                    yield f"data: {json.dumps({'message': msg})}\n\n"
            except queue.Empty:
                # If queue is empty, send heartbeat to keep connection
                yield f"data: {json.dumps({'heartbeat': True})}\n\n"
                
            time.sleep(0.1)  # Prevent CPU overuse
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/update_ntp_servers', methods=['POST'])
@login_required
def update_ntp_servers():
    """API endpoint to update the list of NTP servers and save to config"""
    try:
        # Get the list of servers from the request
        data = request.json
        if not data or 'servers' not in data or not isinstance(data['servers'], list):
            return jsonify({"success": False, "error": "Invalid server list format"})
        
        if not data['servers']:
            return jsonify({"success": False, "error": "Server list cannot be empty"})
        
        # Filter out empty servers and create a unique list
        unique_servers = []
        for server in data['servers']:
            if server.strip() and server.strip() not in unique_servers:
                unique_servers.append(server.strip())
        
        # Update sensor_system NTP_SERVERS
        sensor_system.NTP_SERVERS = unique_servers
        
        # Update config file
        config = load_config()
        config['ntp_servers'] = unique_servers
        save_config(config)
        
        logger.info(f"NTP server list updated and saved to config: {', '.join(unique_servers)}")
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Failed to update NTP servers: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/reboot_system', methods=['POST'])
@login_required
def reboot_system():
    """API endpoint to reboot the Raspberry Pi"""
    try:
        logger.warning("System reboot initiated from web interface")
        
        # Use subprocess to run the reboot command
        # This command requires sudo privileges, which should be set up for the user running the script
        reboot_command = ["sudo", "reboot"]
        
        # Execute the command in a non-blocking way
        subprocess.Popen(reboot_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Failed to reboot system: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/kill_script', methods=['POST'])
@login_required
def kill_script():
    """API endpoint to kill the main script process"""
    try:
        logger.warning("Script termination initiated from web interface")
        
        # Log a goodbye message
        logger.info("Exiting gracefully. To restart the script, SSH into the Raspberry Pi.")
        
        # Schedule the script to exit after sending the response
        def delayed_exit():
            time.sleep(2)  # Give time for the response to be sent
            os._exit(0)  # Force exit the process
        
        # Start the delayed exit in a separate thread
        exit_thread = threading.Thread(target=delayed_exit)
        exit_thread.daemon = True
        exit_thread.start()
        
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Failed to terminate script: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/shutdown_system', methods=['POST'])
@login_required
def shutdown_system():
    """API endpoint to safely shut down the Raspberry Pi"""
    try:
        logger.warning("System shutdown initiated from web interface")
        
        # Use subprocess to run the shutdown command
        # This command requires sudo privileges, which should be set up for the user running the script
        shutdown_command = ["sudo", "shutdown", "-h", "now"]
        
        # Execute the command in a non-blocking way
        subprocess.Popen(shutdown_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Failed to shutdown system: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/save_direct_mode', methods=['POST'])
@login_required
def save_direct_mode():
    """API endpoint to save direct mode setting to config file"""
    try:
        data = request.get_json()
        direct_mode = data.get('direct_mode', False)
        
        # Update sensor system state immediately
        sensor_system.DIRECT_MODE = direct_mode
        
        # Update config file
        config = load_config()
        config['direct_mode'] = direct_mode
        save_config(config)
        
        logger.info(f"Direct mode setting updated to {'ON' if direct_mode else 'OFF'} and saved to config")
        return jsonify({"success": True, "message": "Direct mode setting saved"})
    except Exception as e:
        logger.error(f"Failed to save direct mode setting: {e}")
        return jsonify({"success": False, "error": str(e)})

# --- SC7A20H Calibration Endpoints ---

@app.route('/api/start_calibration', methods=['POST'])
@login_required
def start_calibration_endpoint():
    """API endpoint to start SC7A20H calibration"""
    if not sensor_system:
        return jsonify({"success": False, "error": "Sensor system not initialized"}), 500
    
    success = sensor_system.start_calibration()
    if success:
        return jsonify({"success": True, "message": "Calibration started"})
    else:
        # Check status to provide more specific error
        status = sensor_system.get_calibration_status()
        error_msg = status.get("status_text", "Failed to start calibration (unknown reason)")
        if "already in progress" in error_msg.lower():
             return jsonify({"success": False, "error": "Calibration is already in progress."}), 409 # Conflict
        elif "not initialized" in error_msg.lower():
            return jsonify({"success": False, "error": "Sensor not initialized. Cannot calibrate."}), 503 # Service Unavailable
        else:
             return jsonify({"success": False, "error": error_msg}), 500

@app.route('/api/calibration_status')
@login_required
def get_calibration_status_endpoint():
    """API endpoint to get SC7A20H calibration status and sensor readings"""
    if not sensor_system:
        return jsonify({"error": "Sensor system not initialized"}), 500
        
    status_data = sensor_system.get_calibration_status()
    return jsonify(status_data)

@app.route('/api/update_deadzone', methods=['POST'])
@login_required
def update_deadzone_endpoint():
    """API endpoint to update the SC7A20H deadzone percentage"""
    if not sensor_system:
        return jsonify({"success": False, "error": "Sensor system not initialized"}), 500

    try:
        data = request.get_json()
        deadzone_percent = data.get('deadzone_percent')
        
        if deadzone_percent is None:
            return jsonify({"success": False, "error": "Missing 'deadzone_percent' parameter"}), 400

        success, message = sensor_system.update_deadzone(deadzone_percent)
        
        if success:
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "error": message}), 400 # Bad request if value is invalid

    except Exception as e:
        logger.error(f"Failed to update deadzone: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

def load_config():
    """Load configuration from file or create with defaults if it doesn't exist"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                logger.info(f"Configuration loaded from {CONFIG_FILE}")
                return config
        else:
            # Create config file with defaults
            with open(CONFIG_FILE, 'w') as f:
                json.dump(DEFAULT_CONFIG, f, indent=4)
                logger.info(f"Created default configuration file at {CONFIG_FILE}")
                return DEFAULT_CONFIG.copy()
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return DEFAULT_CONFIG.copy()

def save_config(config):
    """Save configuration to file"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
            logger.info(f"Configuration saved to {CONFIG_FILE}")
        return True
    except Exception as e:
        logger.error(f"Failed to save configuration: {e}")
        return False

def run_web_server():
    """Run the Flask web server"""
    app.run(host='0.0.0.0', port=8080, threaded=True)

if __name__ == "__main__":
    # This file should not be run directly, but if it is,
    # demonstrate how it would work with mock data
    class MockSensorSystem:
        def __init__(self):
            self.SIDE = 2
            self.DIRECT_MODE = False
            self.DEBUG_MODE = True
            self.NTP_SERVERS = [
                "pool.ntp.org",
                "time.google.com",
                "time.apple.com"
            ]
            
        def try_ntp_sync(self):
            class MockNTPResponse:
                def __init__(self):
                    self.tx_time = time.time()
                    self.server = "mock.ntp.org"
            return MockNTPResponse()
            
        def trigger_start_event(self):
            logger.info("Mock START event triggered")
            
        def trigger_finish_event(self):
            logger.info("Mock FINISH event triggered")
    
    # Initialize with mock data
    initialize_web_server(MockSensorSystem())
    
    # Run the web server
    logger.info("Starting web server in standalone mode with mock data")
    run_web_server() 