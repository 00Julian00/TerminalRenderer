import asyncio
import time
import atexit
import argparse
import logging
import cProfile
import pickle
import socket
import json
import queue

from blessed import Terminal
import numpy as np
import sounddevice as sd
from pydub import AudioSegment

import logger
import data
import terminal_api
import renderer
import elements
import video_processing

terminal = Terminal()

active_elements: list[elements.Element] = []

# Socket for sending daemon messages
daemon_sock = None
daemon_port = 9999
daemon_host = '127.0.0.1'

class FrameSyncAudioPlayer:
    def __init__(self, sample_rate, samples_per_frame):
        self.sample_rate = sample_rate
        self.samples_per_frame = samples_per_frame
        self.queue = queue.Queue(maxsize=10)  # Buffer a few chunks
        self.stream = None
        self.finished = False
        
    def callback(self, outdata, frames, time_info, status):
        try:
            # Get next chunk from queue (non-blocking)
            chunk = self.queue.get_nowait()
            
            if len(chunk) <= frames:
                outdata[:len(chunk), 0] = chunk
                outdata[len(chunk):, 0] = 0
            else:
                outdata[:frames, 0] = chunk[:frames]
        except queue.Empty:
            # No chunk available, output silence
            outdata[:, 0] = 0
    
    def play_chunk(self, chunk):
        """Queue a chunk to be played"""
        try:
            self.queue.put(chunk, block=False)
        except queue.Full:
            pass  # Skip if queue is full
    
    def start(self):
        self.stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=1,
            callback=self.callback,
            blocksize=self.samples_per_frame
        )
        # self.stream.start()
    
    def stop(self):
        self.finished = True
        if self.stream:
            self.stream.stop()
            self.stream.close()

def send_daemon_message(daemon_msg: data.DaemonMessage):
    """Send a daemon message to the daemon terminal"""
    global daemon_sock
    if daemon_sock is None:
        return
    
    try:
        msg_dict = {
            'frames_shown': daemon_msg.frames_shown,
            'total_frames': daemon_msg.total_frames,
            'idle_time_per_frame': daemon_msg.idle_time_per_frame,
            'data_throughput': daemon_msg.data_throughput,
            'playback_speed': daemon_msg.playback_speed
        }
        json_msg = json.dumps(msg_dict)
        daemon_sock.sendto(json_msg.encode('utf-8'), (daemon_host, daemon_port))
    except Exception:
        pass  # Silently ignore if daemon is not available

async def watch_terminal_dimensions(should_refresh: bool = True):
    delay = 1.0 / 30
    prev_width, prev_height = terminal.width, terminal.height

    while True:
        await asyncio.sleep(delay)

        width, height = terminal.width, terminal.height
        
        if width != prev_width or height != prev_height:
            prev_width, prev_height = width, height
            renderer.on_terminal_size_change(terminal, should_refresh)

            for element in active_elements:
                element.on_terminal_size_change(data.Size(width, height))

async def _play_video(file_path: str, ascii_mode: bool = False, size: int = 32, debug_mode: bool = False):
    global terminal, daemon_sock

    is_preprocessed = file_path.lower().endswith((".pickle", ".pkl"))

    audio_player = None
    sample_rate = None

    if is_preprocessed:
        processed_video: data.ProcessedVideo
        with open(file_path, "rb") as f:
            processed_video = pickle.load(f)

        frame_generator = processed_video.consume_frames()
    else:
        audio = AudioSegment.from_file(file_path)
        audio_data = np.array(audio.get_array_of_samples(), dtype=np.float32)
        
        # Normalize based on sample width
        if audio.sample_width == 2:  # 16-bit audio
            audio_data = audio_data / 32768.0
        elif audio.sample_width == 1:  # 8-bit audio
            audio_data = (audio_data - 128) / 128.0
        elif audio.sample_width == 4:  # 32-bit audio
            audio_data = audio_data / 2147483648.0
        
        audio_data = audio_data.reshape((-1, 2))  # Reshape for stereo
        audio_data = audio_data.mean(axis=1)  # Convert to mono

        sample_rate = audio.frame_rate

    atexit.register(terminal_api.show_cursor, terminal)
    atexit.register(terminal_api.reset_text_color, terminal)

    asyncio.create_task(watch_terminal_dimensions(not is_preprocessed))

    terminal_api.hide_cursor(terminal)
    terminal_api.clear_screen(terminal)

    framerate = video_processing.get_framerate(file_path) if not is_preprocessed else processed_video.framerate

    samples_per_frame = int(sample_rate / framerate) if not is_preprocessed else 0
    audio_chunks = []

    if not is_preprocessed:
        for i in range(video_processing.get_frame_amount(file_path)):
            start_sample = i * samples_per_frame
            end_sample = start_sample + samples_per_frame
            chunk = audio_data[start_sample:end_sample]
            audio_chunks.append(chunk)
        
        # Initialize audio player with sample rate and frame size
        if audio_chunks:
            audio_player = FrameSyncAudioPlayer(sample_rate, samples_per_frame)
            audio_player.start()
    
    try:
        if debug_mode:
            logger.start_external_log()
            # Initialize daemon socket for sending stats
            daemon_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        else:
            logging.getLogger().setLevel(logging.ERROR)

        coords = elements.element_COORDINATES(
            color=data.Color(1.0, 1.0, 1.0)
        )

        fps = elements.element_FPS(
            color=data.Color(0.0, 1.0, 0.0)
        )

        if not is_preprocessed:
            vid = elements.element_VIDEO(
                video_path=file_path,
                render_as_ascii=ascii_mode,
                size=size
            )

            active_elements.extend([vid])

        if debug_mode and not is_preprocessed:
            active_elements.extend([coords, fps])

        # Generate initial data
        for element in active_elements:
            element.on_terminal_size_change(data.Size(terminal.width, terminal.height))

        # Main render loop
        frame_time = 1.0 / framerate  # Target: 33.33ms per frame
        
        # Stats tracking
        frame_idx = 0
        total_frames = len(processed_video.frames) if is_preprocessed else video_processing.get_frame_amount(file_path)  # For preprocessed videos
        last_sleep_time = 0.0

        # Main render loop
        while True:
            frame_start = time.time()
            
            # Get the output string from renderer
            output_string = ""
            if not is_preprocessed:
                # Queue the audio chunk for this frame
                if audio_player and frame_idx < len(audio_chunks):
                    audio_player.play_chunk(audio_chunks[frame_idx])
                output_string = renderer.render(active_elements, terminal)
            else:
                next_frame = next(frame_generator, None)
                output_string = next_frame
            
            # Print the output to terminal
            if output_string:
                terminal_api.print_at(terminal, (0, 0), output_string)
            
            # Measure bytes sent (data throughput per frame in KB)
            bytes_sent = len(output_string.encode('utf-8'))
            data_throughput_per_frame = bytes_sent / 1024  # KB per frame
            
            # Calculate how long to sleep
            elapsed = time.time() - frame_start
            sleep_time = max(0, frame_time - elapsed)
            
            # Calculate playback speed (current fps / video framerate)
            actual_frame_time = elapsed + sleep_time
            actual_fps = 1.0 / actual_frame_time if actual_frame_time > 0 else 0.0
            playback_speed = actual_fps / framerate if framerate > 0 else 0.0
            
            frame_idx += 1
            
            # Send daemon message if in debug mode
            if debug_mode and daemon_sock:
                daemon_msg = data.DaemonMessage(
                    frames_shown=frame_idx,
                    total_frames=total_frames,
                    idle_time_per_frame=last_sleep_time,  # Sleep time from last round
                    data_throughput=data_throughput_per_frame,  # KB per frame
                    playback_speed=playback_speed
                )
                send_daemon_message(daemon_msg)

            logging.info(f"Frame time: {elapsed:.4f}s, sleeping for {sleep_time:.4f}s")
            
            # Store sleep time for next iteration
            last_sleep_time = sleep_time
            
            await asyncio.sleep(sleep_time)

    except Exception as e:
        if audio_player:
            audio_player.stop()
        terminal_api.show_cursor(terminal)
        terminal_api.reset_text_color(terminal)
        terminal_api.clear_screen(terminal)
        raise e

    finally:
        if audio_player:
            audio_player.stop()
        terminal_api.show_cursor(terminal)
        terminal_api.reset_text_color(terminal)
        terminal_api.clear_screen(terminal)
        if logger.log_manager:
            logger.log_manager.cleanup()
        time.sleep(0.5)  # Brief pause to ensure cleanup completes

def play_video(file_path: str, ascii_mode: bool = False, size: int = 32, debug_mode: bool = False):
    try:    
        asyncio.run(_play_video(file_path, ascii_mode, size, debug_mode))
    except KeyboardInterrupt:
        terminal_api.show_cursor(terminal)
        terminal_api.reset_text_color(terminal)
        terminal_api.clear_screen(terminal)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Play a video in the terminal.")
    parser.add_argument("file_path", help="The path to the video file.")
    parser.add_argument("--size", type=int, default=32, help="The size of the video element.")
    parser.add_argument("--ascii", action="store_true", help="Render video as ASCII.")
    parser.add_argument("--debug", action="store_true", help="Show debug overlay.")
    args = parser.parse_args()

    if args.debug:
        cProfile.run('play_video(args.file_path, args.ascii, args.size, args.debug)')
    else:
        play_video(args.file_path, args.ascii, args.size, args.debug)