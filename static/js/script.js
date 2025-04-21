// Global variables
let autoRefreshEnabled = true;
let refreshTimer;
let logSocket = null;
let logPaused = false;
let connectionLost = false;
let sensorStatusIntervalId = null;

// DOM Ready function
document.addEventListener('DOMContentLoaded', function() {
    // Initialize page
    initPage();
    
    // Setup auto-refresh
    setupAutoRefresh();
    
    // Scroll log container to bottom
    scrollLogToBottom();
});

function initPage() {
    // Hide all panels at start
    hideAllPanels();
    
    // Set up tab navigation
    setupTabs();
    
    // Set up match detail toggles if on matches tab
    setupMatchDetailToggles();
    
    // Set up clear matches functionality
    setupClearMatches();
    
    // Initialize sensor tab functionality
    initSensorsTab();
    
    // System buttons event listeners
    const ntpForm = document.getElementById('ntp-sync-form');
    const syncNtpButton = document.getElementById('sync-ntp');
    const ntpEditButton = document.getElementById('edit-ntp');
    const saveNtpButton = document.getElementById('save-ntp-servers');
    const cancelNtpButton = document.getElementById('cancel-ntp-servers');
    
    // NTP sync button
    if (syncNtpButton) {
        syncNtpButton.addEventListener('click', syncNtpTime);
    }
    
    // NTP edit button
    if (ntpEditButton) {
        ntpEditButton.addEventListener('click', function() {
            document.getElementById('ntp-servers-editor').style.display = 'block';
            hideAllPanels(['ntp-servers-editor']);
        });
    }
    
    // Save NTP servers button
    if (saveNtpButton) {
        saveNtpButton.addEventListener('click', saveNtpServers);
    }
    
    // Cancel NTP server edit button
    if (cancelNtpButton) {
        cancelNtpButton.addEventListener('click', function() {
            document.getElementById('ntp-servers-editor').style.display = 'none';
        });
    }
    
    // Add direct mode toggle
    const directModeToggle = document.getElementById('direct-mode-toggle');
    if (directModeToggle) {
        directModeToggle.addEventListener('change', function() {
            // Just update the visual indicator
            const status = document.getElementById('direct-mode-status');
            if (status) {
                status.textContent = this.checked ? 'ON' : 'OFF';
            }
        });
    }
    
    // Add save direct mode button listener
    const saveDirectMode = document.getElementById('save-direct-mode');
    if (saveDirectMode) {
        saveDirectMode.addEventListener('click', saveDirectModeSettings);
    }
    
    // Add reboot button listener
    const rebootSystem = document.getElementById('reboot-system');
    if (rebootSystem) {
        rebootSystem.addEventListener('click', function() {
            document.getElementById('reboot-confirm').style.display = 'block';
            hideAllPanels(['reboot-confirm']);
        });
    }
    
    // Add reboot confirmation listeners
    const confirmReboot = document.getElementById('confirm-reboot');
    if (confirmReboot) {
        confirmReboot.addEventListener('click', rebootRaspberryPi);
    }
    
    const cancelReboot = document.getElementById('cancel-reboot');
    if (cancelReboot) {
        cancelReboot.addEventListener('click', function() {
            document.getElementById('reboot-confirm').style.display = 'none';
        });
    }
    
    // Add shutdown button listener
    const shutdownSystem = document.getElementById('shutdown-system');
    if (shutdownSystem) {
        shutdownSystem.addEventListener('click', function() {
            document.getElementById('shutdown-confirm').style.display = 'block';
            hideAllPanels(['shutdown-confirm']);
        });
    }
    
    // Add shutdown confirmation listeners
    const confirmShutdown = document.getElementById('confirm-shutdown');
    if (confirmShutdown) {
        confirmShutdown.addEventListener('click', shutdownRaspberryPi);
    }
    
    const cancelShutdown = document.getElementById('cancel-shutdown');
    if (cancelShutdown) {
        cancelShutdown.addEventListener('click', function() {
            document.getElementById('shutdown-confirm').style.display = 'none';
        });
    }
    
    // Add kill script button listener
    const killScript = document.getElementById('kill-script');
    if (killScript) {
        killScript.addEventListener('click', function() {
            document.getElementById('kill-confirm').style.display = 'block';
            hideAllPanels(['kill-confirm']);
        });
    }
    
    // Add kill script confirmation listeners
    const confirmKill = document.getElementById('confirm-kill');
    if (confirmKill) {
        confirmKill.addEventListener('click', killScriptProcess);
    }
    
    const cancelKill = document.getElementById('cancel-kill');
    if (cancelKill) {
        cancelKill.addEventListener('click', function() {
            document.getElementById('kill-confirm').style.display = 'none';
        });
    }
    
    // Add dangerous options toggle listener
    const dangerousToggle = document.getElementById('toggle-dangerous');
    if (dangerousToggle) {
        dangerousToggle.addEventListener('click', function() {
            const dangerousOptions = document.getElementById('dangerous-options');
            if (dangerousOptions) {
                dangerousOptions.style.display = 'block';
                hideAllPanels(['dangerous-options']);
            }
        });
    }
    
    // Add close button for dangerous options
    const closeDangerous = document.getElementById('close-dangerous');
    if (closeDangerous) {
        closeDangerous.addEventListener('click', function() {
            document.getElementById('dangerous-options').style.display = 'none';
        });
    }
    
    // Add connection banner close button
    const closeBanner = document.getElementById('close-banner');
    if (closeBanner) {
        closeBanner.addEventListener('click', function() {
            document.getElementById('connection-loss-banner').classList.add('hidden');
        });
    }
    
    // Add log control listeners
    const pauseButton = document.getElementById('pause-logs');
    if (pauseButton) {
        pauseButton.addEventListener('click', toggleLogPause);
    }
    
    const clearButton = document.getElementById('clear-logs');
    if (clearButton) {
        clearButton.addEventListener('click', clearLogs);
    }
    
    // Setup AJAX for getting log updates
    setupLogUpdates();
}

function hideAllPanels(exceptPanels = []) {
    // List of all panel IDs
    const allPanels = [
        'ntp-servers-editor',
        'reboot-confirm',
        'kill-confirm',
        'dangerous-options',
        'clear-matches-confirm',
        'shutdown-confirm'
    ];
    
    // Hide all panels except the ones specified
    allPanels.forEach(panelId => {
        if (!exceptPanels.includes(panelId)) {
            const panel = document.getElementById(panelId);
            if (panel) {
                panel.style.display = 'none';
            }
        }
    });
}

function killScriptProcess() {
    const resultElement = document.getElementById('ntp-sync-result');
    resultElement.style.display = 'none';
    
    // Hide the confirmation dialog
    document.getElementById('kill-confirm').style.display = 'none';
    
    fetch('/api/kill_script', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        resultElement.style.display = 'block';
        
        if (data.success) {
            resultElement.className = 'success-message';
            resultElement.innerHTML = 'Script termination initiated. This web interface will no longer be available.';
            
            // Disable all control buttons
            const buttons = document.querySelectorAll('button');
            buttons.forEach(button => {
                button.disabled = true;
            });
            
            // Show countdown message
            setTimeout(() => {
                resultElement.innerHTML = 'Script is terminating. This page will close in 5 seconds...';
                
                // Close page after 5 seconds
                setTimeout(() => {
                    window.close();
                    // In case window.close() doesn't work (most browsers block it)
                    document.body.innerHTML = '<div style="text-align:center;padding:50px;"><h1>Script terminated</h1><p>The script has been terminated. You can close this window.</p></div>';
                }, 5000);
            }, 2000);
            
        } else {
            resultElement.className = 'error-message';
            resultElement.innerHTML = `Failed to terminate script: ${data.error}`;
        }
    })
    .catch(error => {
        resultElement.style.display = 'block';
        resultElement.className = 'error-message';
        resultElement.innerHTML = `Request failed: ${error}`;
    });
}

function setupTabs() {
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            // Deactivate all buttons and content
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));

            // Activate the clicked button and corresponding content
            button.classList.add('active');
            const tabId = button.getAttribute('data-tab');
            const activeContent = document.getElementById(tabId);
            if (activeContent) {
                activeContent.classList.add('active');
            }
            
            // Start/Stop sensor polling based on active tab
            if (tabId === 'sensors-tab') {
                startSensorStatusPolling();
            } else {
                stopSensorStatusPolling();
            }
            
            // Update match details setup if matches tab is activated
            if (tabId === 'matches-tab') {
                setupMatchDetailToggles();
            }
        });
    });
}

function setupMatchDetailToggles() {
    const toggleButtons = document.querySelectorAll('.toggle-details');
    
    toggleButtons.forEach(button => {
        button.addEventListener('click', function() {
            const matchCard = this.closest('.match-card');
            const detailsSection = matchCard.querySelector('.match-details');
            
            // Toggle visibility
            if (detailsSection.classList.contains('visible')) {
                detailsSection.classList.remove('visible');
                this.textContent = 'Details';
            } else {
                detailsSection.classList.add('visible');
                this.textContent = 'Hide Details';
            }
        });
    });
}

function setupAutoRefresh() {
    // Refresh system info every 5 seconds
    refreshTimer = setInterval(refreshSystemInfo, 5000);
}

function refreshSystemInfo() {
    // Fetch and update only the system information
    fetch('/api/system_info')
        .then(response => response.json())
        .then(data => {
            updateSystemInfo(data);
        })
        .catch(error => {
            console.error('Error fetching system info:', error);
        });
}

function updateSystemInfo(data) {
    // Update current time
    document.getElementById('current-time').textContent = data.current_time;
    
    // Update NTP sync info if available
    if (data.last_ntp_sync_time) {
        document.getElementById('last-ntp-sync-time').textContent = data.last_ntp_sync_time;
        document.getElementById('last-ntp-sync-server').textContent = data.last_ntp_sync_server;
    }
}

function setupLogUpdates() {
    // Use server-sent events for log updates
    const evtSource = new EventSource('/api/log_stream');
    logSocket = evtSource;
    
    evtSource.onopen = function() {
        // Hide connection loss banner if it was shown
        if (connectionLost) {
            connectionLost = false;
            document.getElementById('connection-loss-banner').classList.add('hidden');
        }
    };
    
    evtSource.onmessage = function(event) {
        const logData = JSON.parse(event.data);
        
        // Only process if not a heartbeat and logs are not paused
        if (!logData.heartbeat && !logPaused) {
            appendLogEntry(logData);
            
            // Auto-scroll if we're at the bottom
            if (isScrolledToBottom()) {
                scrollLogToBottom();
            }
        }
    };
    
    evtSource.onerror = function() {
        // Show connection loss banner
        connectionLost = true;
        document.getElementById('connection-loss-banner').classList.remove('hidden');
        
        console.error('EventSource failed. Reconnecting in 5 seconds...');
        setTimeout(() => {
            if (logSocket) {
                logSocket.close();
                logSocket = null;
            }
            setupLogUpdates();
        }, 5000);
    };
}

function toggleLogPause() {
    logPaused = !logPaused;
    const pauseButton = document.getElementById('pause-logs');
    
    if (pauseButton) {
        pauseButton.textContent = logPaused ? 'Resume Logs' : 'Pause Logs';
        pauseButton.classList.toggle('btn-warning', logPaused);
    }
}

function clearLogs() {
    const logContainer = document.getElementById('log-container');
    if (logContainer) {
        while (logContainer.firstChild) {
            logContainer.removeChild(logContainer.firstChild);
        }
    }
}

function appendLogEntry(logData) {
    // Skip empty logs or logs without actual content
    if (!logData.message || !logData.message.trim()) {
        return;
    }
    
    // Skip web server access logs (HTTP requests)
    if (logData.message.includes(' - - [') && logData.message.includes('] "GET ') || 
        logData.message.includes(' - - [') && logData.message.includes('] "POST ')) {
        return;
    }
    
    const logContainer = document.getElementById('log-container');
    const logEntry = document.createElement('div');
    logEntry.className = 'log-entry';
    
    // Add appropriate class based on log level
    if (logData.message.includes('ERROR')) {
        logEntry.classList.add('error');
    } else if (logData.message.includes('WARNING')) {
        logEntry.classList.add('warning');
    } else if (logData.message.includes('DEBUG')) {
        logEntry.classList.add('debug');
    } else {
        logEntry.classList.add('info');
    }
    
    // Just display the entire log message normally, no special formatting needed anymore
    logEntry.textContent = logData.message;
    
    logContainer.appendChild(logEntry);
    
    // Limit the number of log entries to prevent memory issues
    while (logContainer.childNodes.length > 1000) {
        logContainer.removeChild(logContainer.firstChild);
    }
}

function isScrolledToBottom() {
    const logContainer = document.getElementById('log-container');
    const scrollPosition = logContainer.scrollTop + logContainer.clientHeight;
    const scrollHeight = logContainer.scrollHeight;
    
    // Consider "at bottom" if within 50px of the bottom
    return (scrollHeight - scrollPosition) < 50;
}

function scrollLogToBottom() {
    const logContainer = document.getElementById('log-container');
    logContainer.scrollTop = logContainer.scrollHeight;
}

function syncNtpTime(event) {
    if (event) {
        event.preventDefault();
    }
    
    const resultElement = document.getElementById('ntp-sync-result');
    resultElement.style.display = 'none';
    
    // Show loading indicator
    const button = document.getElementById('sync-ntp');
    const originalText = button.textContent;
    button.textContent = 'Syncing...';
    button.disabled = true;
    
    fetch('/api/trigger_ntp_sync', {
        method: 'POST',
    })
    .then(response => response.json())
    .then(data => {
        resultElement.style.display = 'block';
        
        if (data.success) {
            resultElement.className = 'success-message';
            resultElement.innerHTML = `NTP time synchronized successfully with ${data.server}`;
            
            // Update displayed time
            document.getElementById('last-ntp-sync-time').textContent = data.time;
            document.getElementById('last-ntp-sync-server').textContent = data.server;
        } else {
            resultElement.className = 'error-message';
            resultElement.innerHTML = `Failed to sync NTP time: ${data.error}`;
        }
        
        // Reset button state
        button.textContent = originalText;
        button.disabled = false;
        
        // Auto-hide message after 5 seconds
        setTimeout(() => {
            resultElement.style.display = 'none';
        }, 5000);
    })
    .catch(error => {
        resultElement.style.display = 'block';
        resultElement.className = 'error-message';
        resultElement.innerHTML = `Request failed: ${error}`;
        
        // Reset button state
        button.textContent = originalText;
        button.disabled = false;
    });
}

function saveNtpServers() {
    const serverList = document.getElementById('ntp-servers-list').value;
    const resultElement = document.getElementById('ntp-sync-result');
    resultElement.style.display = 'none';
    
    fetch('/api/update_ntp_servers', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            servers: serverList.split('\n').filter(server => server.trim() !== '')
        })
    })
    .then(response => response.json())
    .then(data => {
        resultElement.style.display = 'block';
        
        if (data.success) {
            resultElement.className = 'success-message';
            resultElement.innerHTML = 'NTP server list updated successfully.';
            document.getElementById('ntp-servers-editor').style.display = 'none';
        } else {
            resultElement.className = 'error-message';
            resultElement.innerHTML = `Failed to update NTP servers: ${data.error}`;
        }
    })
    .catch(error => {
        resultElement.style.display = 'block';
        resultElement.className = 'error-message';
        resultElement.innerHTML = `Request failed: ${error}`;
    });
}

function rebootRaspberryPi() {
    const resultElement = document.getElementById('ntp-sync-result');
    resultElement.style.display = 'none';
    
    // Hide the confirmation dialog
    document.getElementById('reboot-confirm').style.display = 'none';
    
    fetch('/api/reboot_system', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        resultElement.style.display = 'block';
        
        if (data.success) {
            resultElement.className = 'success-message';
            resultElement.innerHTML = 'System reboot initiated. Please wait while the Raspberry Pi restarts...';
            
            // Disable all control buttons during reboot
            const buttons = document.querySelectorAll('button');
            buttons.forEach(button => {
                button.disabled = true;
            });
            
            // Show reconnecting message
            setTimeout(() => {
                resultElement.innerHTML = 'System is rebooting. This page will attempt to reconnect in 60 seconds...';
                
                // Attempt to reload the page after 60 seconds
                setTimeout(() => {
                    window.location.reload();
                }, 60000);
            }, 5000);
            
        } else {
            resultElement.className = 'error-message';
            resultElement.innerHTML = `Failed to reboot system: ${data.error}`;
        }
    })
    .catch(error => {
        resultElement.style.display = 'block';
        resultElement.className = 'error-message';
        resultElement.innerHTML = `Request failed: ${error}`;
    });
}

function saveDirectModeSettings() {
    const toggle = document.getElementById('direct-mode-toggle');
    const isDirectMode = toggle.checked;
    
    // Send request to server to save the mode setting
    fetch('/api/save_direct_mode', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            direct_mode: isDirectMode
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Show success message
            const resultElement = document.getElementById('ntp-sync-result');
            resultElement.style.display = 'block';
            resultElement.className = 'success-message';
            resultElement.innerHTML = `Direct mode setting saved as ${isDirectMode ? 'DIRECT' : 'PROXY'}. Changes will be applied after reboot.`;
            
            // Auto-hide message after 5 seconds
            setTimeout(() => {
                resultElement.style.display = 'none';
            }, 5000);
        } else {
            // Show error
            const resultElement = document.getElementById('ntp-sync-result');
            resultElement.style.display = 'block';
            resultElement.className = 'error-message';
            resultElement.innerHTML = `Failed to save direct mode setting: ${data.error}`;
        }
    })
    .catch(error => {
        // Show error
        const resultElement = document.getElementById('ntp-sync-result');
        resultElement.style.display = 'block';
        resultElement.className = 'error-message';
        resultElement.innerHTML = `Request failed: ${error}`;
    });
}

function setupClearMatches() {
    // Add clear matches button listener
    const clearMatches = document.getElementById('clear-matches');
    if (clearMatches) {
        clearMatches.addEventListener('click', function() {
            document.getElementById('clear-matches-confirm').style.display = 'block';
            hideAllPanels(['clear-matches-confirm']);
        });
    }
    
    // Add clear matches confirmation listeners
    const confirmClearMatches = document.getElementById('confirm-clear-matches');
    if (confirmClearMatches) {
        confirmClearMatches.addEventListener('click', clearMatchHistory);
    }
    
    const cancelClearMatches = document.getElementById('cancel-clear-matches');
    if (cancelClearMatches) {
        cancelClearMatches.addEventListener('click', function() {
            document.getElementById('clear-matches-confirm').style.display = 'none';
        });
    }
}

function clearMatchHistory() {
    // Hide the confirmation dialog
    document.getElementById('clear-matches-confirm').style.display = 'none';
    
    // Show temporary message
    const matchesContainer = document.getElementById('matches-container');
    if (matchesContainer) {
        matchesContainer.innerHTML = '<div class="processing-message">Clearing match history...</div>';
    }
    
    fetch('/api/clear_matches', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Show success message
            matchesContainer.innerHTML = '<div class="no-matches">Match history cleared successfully.</div>';
            
            // Auto-refresh after 2 seconds to show empty state
            setTimeout(() => {
                location.reload();
            }, 2000);
        } else {
            // Show error
            matchesContainer.innerHTML = `<div class="error-message">Failed to clear match history: ${data.error}</div>`;
        }
    })
    .catch(error => {
        // Show error
        matchesContainer.innerHTML = `<div class="error-message">Request failed: ${error}</div>`;
    });
}

function shutdownRaspberryPi() {
    const resultElement = document.getElementById('ntp-sync-result');
    resultElement.style.display = 'none';
    
    // Hide the confirmation dialog
    document.getElementById('shutdown-confirm').style.display = 'none';
    
    fetch('/api/shutdown_system', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        resultElement.style.display = 'block';
        
        if (data.success) {
            resultElement.className = 'success-message';
            resultElement.innerHTML = 'System shutdown initiated. The Raspberry Pi is shutting down...';
            
            // Disable all control buttons during shutdown
            const buttons = document.querySelectorAll('button');
            buttons.forEach(button => {
                button.disabled = true;
            });
            
            // Show final message
            setTimeout(() => {
                resultElement.innerHTML = 'System is shutting down. You will see a connection lost message when the process is complete. Do not unplug power until then.';
            }, 5000);
            
        } else {
            resultElement.className = 'error-message';
            resultElement.innerHTML = `Failed to shutdown system: ${data.error}`;
        }
    })
    .catch(error => {
        resultElement.style.display = 'block';
        resultElement.className = 'error-message';
        resultElement.innerHTML = `Request failed: ${error}`;
    });
}

function initSensorsTab() {
    const startCalibrationBtn = document.getElementById('start-calibration-btn');
    const saveDeadzoneBtn = document.getElementById('save-deadzone-btn');

    if (startCalibrationBtn) {
        startCalibrationBtn.addEventListener('click', handleStartCalibration);
    }

    if (saveDeadzoneBtn) {
        saveDeadzoneBtn.addEventListener('click', handleSaveDeadzone);
    }

    // Initial status fetch when the tab might be active on load
    if (document.getElementById('sensors-tab').classList.contains('active')) {
        startSensorStatusPolling();
    }
}

function handleStartCalibration() {
    showSensorStatusMessage('info', 'Requesting calibration start...');
    const btn = document.getElementById('start-calibration-btn');
    btn.disabled = true; // Disable button immediately
    document.getElementById('calib-instructions').classList.remove('hidden');

    fetch('/api/start_calibration', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showSensorStatusMessage('success', 'Calibration started! Do not move the sensor.');
                // Status will update via polling
            } else {
                showSensorStatusMessage('error', `Failed to start calibration: ${data.error}`);
                btn.disabled = false; // Re-enable on failure
                document.getElementById('calib-instructions').classList.add('hidden');
            }
            // Start polling immediately after request, regardless of success/fail to get latest status
            startSensorStatusPolling(); 
        })
        .catch(error => {
            showSensorStatusMessage('error', `Error starting calibration: ${error}`);
            btn.disabled = false; // Re-enable on error
            document.getElementById('calib-instructions').classList.add('hidden');
        });
}

function handleSaveDeadzone() {
    const deadzoneInput = document.getElementById('deadzone-percent');
    const deadzoneValue = parseInt(deadzoneInput.value, 10);

    if (isNaN(deadzoneValue) || deadzoneValue < 0 || deadzoneValue > 100) {
        showSensorStatusMessage('error', 'Invalid deadzone value. Please enter a number between 0 and 100.');
        return;
    }

    showSensorStatusMessage('info', 'Saving deadzone...');
    document.getElementById('save-deadzone-btn').disabled = true;

    fetch('/api/update_deadzone', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ deadzone_percent: deadzoneValue })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showSensorStatusMessage('success', data.message);
            } else {
                showSensorStatusMessage('error', `Failed to save deadzone: ${data.error}`);
            }
             document.getElementById('save-deadzone-btn').disabled = false;
             // Fetch status again to confirm update
             fetchSensorStatus(); 
        })
        .catch(error => {
            showSensorStatusMessage('error', `Error saving deadzone: ${error}`);
            document.getElementById('save-deadzone-btn').disabled = false;
        });
}

function fetchSensorStatus() {
    fetch('/api/calibration_status')
        .then(response => response.json())
        .then(data => {
            updateSensorStatusUI(data);
        })
        .catch(error => {
            console.error("Error fetching sensor status:", error);
            // Optional: display an error in the UI
            document.getElementById('sc7a20h-init-status').textContent = 'Error loading status';
             document.getElementById('sc7a20h-calib-status').textContent = 'Error';
             document.getElementById('sc7a20h-threshold').textContent = 'Error';
             document.getElementById('sc7a20h-magnitude').textContent = 'Error';
        });
}

function updateSensorStatusUI(data) {
    const initStatusEl = document.getElementById('sc7a20h-init-status');
    const calibStatusEl = document.getElementById('sc7a20h-calib-status');
    const thresholdEl = document.getElementById('sc7a20h-threshold');
    const magnitudeEl = document.getElementById('sc7a20h-magnitude');
    const deadzoneInput = document.getElementById('deadzone-percent');
    const calibBtn = document.getElementById('start-calibration-btn');
    const calibInstructions = document.getElementById('calib-instructions');

    // Update Init Status (more descriptive)
    if (data.status_text && data.status_text.includes("Sensor not initialized")) {
         initStatusEl.textContent = 'Error: Not Initialized';
         initStatusEl.className = 'error';
         thresholdEl.textContent = 'N/A';
         magnitudeEl.textContent = 'N/A';
         calibBtn.disabled = true;
    } else if (data.status_text && data.status_text.includes("No sensor data")) {
         initStatusEl.textContent = 'Error: No Data';
         initStatusEl.className = 'error';
         thresholdEl.textContent = 'N/A';
         magnitudeEl.textContent = 'N/A';
         calibBtn.disabled = true;
    } else {
         initStatusEl.textContent = 'Initialized OK';
         initStatusEl.className = 'success';
         calibBtn.disabled = data.is_calibrating; // Disable only if calibrating
    }
    
    // Update Calibration Status Text
    calibStatusEl.textContent = data.status_text || 'Unknown';
    if (data.status_text && data.status_text.toLowerCase().includes('error')) {
        calibStatusEl.classList.add('error');
        calibStatusEl.classList.remove('info', 'success');
    } else if (data.is_calibrating) {
         calibStatusEl.classList.add('info');
         calibStatusEl.classList.remove('error', 'success');
    } else {
         calibStatusEl.classList.add('success');
         calibStatusEl.classList.remove('error', 'info');
    }

    // Update Threshold
    thresholdEl.textContent = data.noise_threshold !== null ? data.noise_threshold.toFixed(4) : 'N/A';

    // Update Current Magnitude
    magnitudeEl.textContent = data.current_magnitude !== null ? data.current_magnitude.toFixed(4) : 'N/A';

    // Update Deadzone Input
    if (deadzoneInput && data.deadzone_percent !== null) {
        // Only update if the input doesn't currently have focus to avoid user typing interruption
        if (document.activeElement !== deadzoneInput) {
            deadzoneInput.value = data.deadzone_percent;
        }
    }

    // Update Calibration Button state and instructions visibility
    calibBtn.disabled = data.is_calibrating;
    if (data.is_calibrating) {
        calibInstructions.classList.remove('hidden');
    } else {
        calibInstructions.classList.add('hidden');
    }
}

function showSensorStatusMessage(type, message) {
    const messageEl = document.getElementById('sc7a20h-status-message');
    messageEl.textContent = message;
    messageEl.className = `status-message ${type}`; // Reset classes and add new type
    messageEl.classList.remove('hidden');

    // Optional: Auto-hide after a few seconds
    setTimeout(() => {
        messageEl.classList.add('hidden');
    }, 5000);
}

function startSensorStatusPolling() {
    if (sensorStatusIntervalId === null) {
        console.log("Starting sensor status polling.");
        fetchSensorStatus(); // Fetch immediately
        sensorStatusIntervalId = setInterval(fetchSensorStatus, 2000); // Poll every 2 seconds
    }
}

function stopSensorStatusPolling() {
    if (sensorStatusIntervalId !== null) {
        console.log("Stopping sensor status polling.");
        clearInterval(sensorStatusIntervalId);
        sensorStatusIntervalId = null;
    }
} 