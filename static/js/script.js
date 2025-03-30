// Global variables
let autoRefreshEnabled = true;
let refreshTimer;
let logSocket = null;
let logPaused = false;
let connectionLost = false;

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
        'dangerous-options'
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
    
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Remove active class from all buttons and content
            document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
            
            // Add active class to clicked button
            this.classList.add('active');
            
            // Show corresponding content
            const tabId = this.getAttribute('data-tab');
            document.getElementById(tabId).classList.add('active');
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