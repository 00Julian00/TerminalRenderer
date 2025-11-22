"""
Log Receiver Daemon - Dependent on parent process
Automatically terminates when parent process ends
"""

import socket
import sys
import argparse
import os
import time
import threading
import json
from blessed import Terminal

from terminal_api import clear_and_print_at, hide_cursor

class LogReceiverDaemon:
    def __init__(self, port=9999, host='127.0.0.1', parent_pid=None):
        self.port = port
        self.host = host
        self.parent_pid = parent_pid
        self.sock = None
        self.running = True
        self.term = Terminal()
        self.daemon_stats = {
            'frames_shown': 0,
            'total_frames': 0,
            'frames_buffered': 0.0,
            'data_throughput': 0.0,
            'playback_speed': 0.0
        }
        hide_cursor()
        
    def check_parent_alive(self):
        """Check if parent process is still running"""
        if self.parent_pid is None:
            return True
            
        try:
            if sys.platform == 'win32':
                import psutil
                return psutil.pid_exists(self.parent_pid)
            else:
                # Unix: send signal 0 to check if process exists
                os.kill(self.parent_pid, 0)
                return True
        except (OSError, ImportError):
            return False
            
    def parent_monitor(self):
        """Monitor parent process in a separate thread"""
        while self.running:
            if not self.check_parent_alive():
                self.running = False
                break
            time.sleep(1)
            
    def setup_socket(self):
        """Initialize the UDP socket"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))
        self.sock.settimeout(2)  # Short timeout for checking shutdown
    
    def display_stats(self):
        """Display stats"""
        # Calculate playback speed as percentage
        playback_speed_percent = self.daemon_stats['playback_speed'] * 100
        
        # Color playback speed: red if below 100%, green otherwise
        if playback_speed_percent < 100:
            playback_speed_color = self.term.red
        else:
            playback_speed_color = self.term.green
        
        frames_buffered = int(self.daemon_stats['frames_buffered'])
        if frames_buffered > 16:
            idle_time_color = self.term.green
        elif frames_buffered > 1:
            idle_time_color = self.term.yellow
        else:
            idle_time_color = self.term.red
        
        # Build the stats display
        stats_text = f"{self.term.bold}Video Playback Statistics:{self.term.normal}\n"
        stats_text += f"Frames Shown:{self.term.normal} {min(int(self.daemon_stats['frames_shown']), int(self.daemon_stats['total_frames']))}\n"
        stats_text += f"Total Frames:{self.term.normal} {self.daemon_stats['total_frames']}\n"
        stats_text += f"Playback Speed:{self.term.normal} {playback_speed_color}{playback_speed_percent:.2f}%{self.term.normal}\n"
        stats_text += f"Frames Buffered:{self.term.normal} {idle_time_color}{frames_buffered}{self.term.normal}\n"
        stats_text += f"Data Throughput:{self.term.normal} {self.daemon_stats['data_throughput']:.2f} KB/frame"

        # Create progress bar
        progress_bar = self.create_progress_bar()

        # Position progress bar at the bottom of the terminal
        final_output = stats_text + self.term.move(self.term.height - 1, 0) + progress_bar

        # Print the combined string in one go
        clear_and_print_at(self.term, (0, 0), final_output)
    
    def create_progress_bar(self):
        """Create a progress bar spanning the entire terminal width"""
        terminal_width = self.term.width
        frames_shown = self.daemon_stats['frames_shown']
        total_frames = self.daemon_stats['total_frames']
        
        if total_frames == 0:
            # No frames yet, show empty progress bar
            return '-' * terminal_width
        
        # Calculate the position of the playhead
        progress_ratio = frames_shown / total_frames
        playhead_position = int(progress_ratio * terminal_width)
        
        # Clamp playhead position to valid range
        playhead_position = max(0, min(terminal_width - 1, playhead_position))
        
        # Build the progress bar
        # Part that has played (before playhead): em-dashes
        played_part = '—' * playhead_position
        # Playhead: *
        playhead = '*'
        # Part that hasn't played yet (after playhead): regular dashes
        remaining_chars = terminal_width - playhead_position - 1
        unplayed_part = '-' * max(0, remaining_chars)
        
        progress_bar = played_part + playhead + unplayed_part
        
        # Ensure the progress bar is exactly terminal_width characters
        # (handle potential encoding issues with em-dash)
        if len(progress_bar) > terminal_width:
            progress_bar = progress_bar[:terminal_width]
        elif len(progress_bar) < terminal_width:
            progress_bar = progress_bar + '-' * (terminal_width - len(progress_bar))
        
        return progress_bar
    
    def parse_message(self, message: str):
        """Parse incoming message - could be JSON stats or regular log"""
        try:
            # Try to parse as JSON first
            data = json.loads(message)
            if all(key in data for key in ['frames_shown', 'total_frames', 'frames_buffered', 'data_throughput', 'playback_speed']):
                # This is a daemon stats message
                self.daemon_stats = data
                self.display_stats()
                return
        except (json.JSONDecodeError, ValueError):
            pass

        sys.stdout.flush()
        
    def run(self):
        """Main daemon loop"""
        self.setup_socket()
        
        # Start parent monitoring thread if parent PID provided
        if self.parent_pid:
            monitor_thread = threading.Thread(target=self.parent_monitor, daemon=True)
            monitor_thread.start()
        
        try:
            while self.running:
                try:
                    data, addr = self.sock.recvfrom(4096)
                    message = data.decode('utf-8')
                    self.parse_message(message)
                except socket.timeout:
                    continue  # Check if still running
                except Exception:
                    pass  # Silently ignore errors
                    
        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup()
            
    def cleanup(self):
        """Clean up resources"""
        self.running = False
        if self.sock:
            self.sock.close()
        sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description='Log Receiver Daemon')
    parser.add_argument('--port', type=int, default=9999,
                       help='Port to listen on (default: 9999)')
    parser.add_argument('--host', default='127.0.0.1',
                       help='Host to bind to (default: 127.0.0.1)')
    parser.add_argument('--parent-pid', type=int, default=None,
                       help='Parent process PID to monitor')
    
    args = parser.parse_args()
    
    daemon = LogReceiverDaemon(
        port=args.port,
        host=args.host,
        parent_pid=args.parent_pid
    )
    
    daemon.run()

if __name__ == '__main__':
    main()
