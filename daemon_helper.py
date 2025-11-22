"""
Daemon helper module for managing the daemon terminal and sending updates
Consolidates all daemon-related functionality including process management,
logging, and status updates.
"""

import socket
import subprocess
import logging
import sys
import time
import os
import atexit
import signal
import json
from pathlib import Path

class TerminalLogHandler(logging.Handler):
    """Custom handler that sends plain text logs via UDP"""
    
    def __init__(self, host='127.0.0.1', port=9999):
        super().__init__()
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
    def emit(self, record):
        try:
            msg = self.format(record)
            self.sock.sendto((msg + '\n').encode('utf-8'), (self.host, self.port))
        except Exception:
            self.handleError(record)
            
    def close(self):
        self.sock.close()
        super().close()

class DaemonManager:
    """Manages the daemon terminal process, logging, and status updates"""
    
    def __init__(self, port=9999, start_daemon=True):
        self.port = port
        self.daemon_process = None
        self.logger = None
        self.terminal_handler = None
        self.daemon_sock = None
        self.is_initialized = False
        
        if start_daemon:
            self.start_daemon_terminal()
            
        self.setup_logger()
        self.initialize_daemon_socket()
        
        # Register cleanup handlers
        atexit.register(self.cleanup)
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)  # Handle Ctrl+C
        if sys.platform != 'win32':
            signal.signal(signal.SIGHUP, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle termination signals"""
        self.cleanup()
        sys.exit(0)
        
    def start_daemon_terminal(self):
        """Start the daemon in a new terminal window as a true child process"""
        daemon_script = Path(__file__).parent / 'daemon_terminal.py'
        
        if not daemon_script.exists():
            return
        
        # Get current process PID to pass to daemon
        parent_pid = os.getpid()
        
        if sys.platform == 'win32':
            # Windows: Start terminal as a child process that will close automatically
            cmd = [
                'python', str(daemon_script),
                '--port', str(self.port),
                '--parent-pid', str(parent_pid)
            ]
            
            # Start terminal as a true child process
            self.daemon_process = subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            
        elif sys.platform == 'darwin':
            # macOS: Use Terminal but as a child process
            script_content = f'''
            tell application "Terminal"
                set newWindow to do script "python3 {daemon_script} --port {self.port} --parent-pid {parent_pid}"
                delay 0.5
            end tell
            '''
            self.daemon_process = subprocess.Popen(
                ['osascript', '-e', script_content]
            )
            
        else:
            # Linux: Start terminal directly as child process
            cmd_args = [
                'python3', str(daemon_script),
                '--port', str(self.port),
                '--parent-pid', str(parent_pid)
            ]
            
            terminals = [
                ['gnome-terminal', '--wait', '--'] + cmd_args,
                ['xterm', '-e'] + cmd_args,
                ['konsole', '-e'] + cmd_args,
                ['x-terminal-emulator', '-e'] + cmd_args,
            ]
            
            for term_cmd in terminals:
                try:
                    self.daemon_process = subprocess.Popen(term_cmd)
                    break
                except FileNotFoundError:
                    continue
            else:
                # Fallback: run without terminal
                self.daemon_process = subprocess.Popen(cmd_args)
        
    def setup_logger(self):
        """Configure the logger with terminal handler"""
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.DEBUG)
        
        # Remove any existing handlers
        self.logger.handlers.clear()
        
        # Add terminal handler
        self.terminal_handler = TerminalLogHandler('127.0.0.1', self.port)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.terminal_handler.setFormatter(formatter)
        self.logger.addHandler(self.terminal_handler)
        
    def initialize_daemon_socket(self):
        """Initialize the daemon socket for sending stats"""
        if not self.is_initialized:
            self.daemon_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.is_initialized = True
        
    def get_logger(self):
        """Get the configured logger"""
        return self.logger
    
    def redirect_stderr(self):
        """Redirect stderr to logger"""
        class StderrToLogger:
            def __init__(self, logger, level):
                self.logger = logger
                self.level = level
                self.buffer = ''
                
            def write(self, msg):
                self.buffer += msg
                if '\n' in self.buffer:
                    lines = self.buffer.split('\n')
                    for line in lines[:-1]:
                        if line.strip():
                            self.logger.log(self.level, f"STDERR: {line.strip()}")
                    self.buffer = lines[-1]
                    
            def flush(self):
                if self.buffer.strip():
                    self.logger.log(self.level, f"STDERR: {self.buffer.strip()}")
                    self.buffer = ''
        
        sys.stderr = StderrToLogger(self.logger, logging.ERROR)
    
    def update_daemon(self, frames_shown: int, total_frames: int, frames_buffered: float, 
                      data_throughput: float, playback_speed: float):
        """
        Send a status update to the daemon terminal.
        
        Args:
            frames_shown: Number of frames shown so far
            total_frames: Total number of frames in the video
            frames_buffered: Number of frames buffered
            data_throughput: Data throughput per frame (in KB)
            playback_speed: Current playback speed ratio (actual fps / target fps)
        """
        if self.daemon_sock is None:
            return
        try:
            msg_dict = {
                'frames_shown': frames_shown,
                'total_frames': total_frames,
                'frames_buffered': frames_buffered,
                'data_throughput': data_throughput,
                'playback_speed': playback_speed
            }
            json_msg = json.dumps(msg_dict)
            self.daemon_sock.sendto(json_msg.encode('utf-8'), ('127.0.0.1', self.port))
        except Exception:
            pass  # Silently ignore if daemon is not available
        
    def cleanup(self):
        """Clean up resources and terminate daemon"""
        # Close daemon socket
        if self.daemon_sock:
            self.daemon_sock.close()
            self.daemon_sock = None
            self.is_initialized = False
        
        # Close handler
        if self.terminal_handler:
            self.terminal_handler.close()
            
        # Terminate daemon process
        if self.daemon_process:
            try:
                if sys.platform == 'win32':
                    self.daemon_process.terminate()
                    time.sleep(0.5)
                    if self.daemon_process.poll() is None:
                        self.daemon_process.kill()
                else:
                    self.daemon_process.terminate()
                    try:
                        self.daemon_process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        self.daemon_process.kill()
            except:
                pass


# Global daemon manager for cleanup
daemon_manager = None

def start_daemon(port=9999):
    """
    Initialize and start the daemon terminal with all functionality.
    This is the single entry point for daemon initialization.
    
    Args:
        port: The UDP port to use for communication (default: 9999)
        
    Returns:
        DaemonManager: The daemon manager instance
    """
    global daemon_manager
    
    # Initialize daemon manager (starts daemon process, sets up logging, initializes socket)
    daemon_manager = DaemonManager(port=port, start_daemon=True)
    
    # Redirect stderr to logger
    daemon_manager.redirect_stderr()
    
    return daemon_manager
