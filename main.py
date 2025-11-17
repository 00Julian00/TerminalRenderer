import argparse
import cProfile
import asyncio
import logging
import time
import pickle

from blessed import Terminal

import terminal_api
from processing_pipeline import VideoProcessor
import daemon_helper
from video_processing import get_framerate, get_frame_amount
from data import ProcessedVideo
# from audio_player import prepare_audio, AudioPlayer

terminal = Terminal()

processor = VideoProcessor()

# audio_player: AudioPlayer = None

async def _play_video(file_path: str, ascii_mode: bool = False, size: int = 32, debug_mode: bool = False):
    frame_idx = 0

    if file_path.endswith('.pkl') or file_path.endswith('.pickle'):
        with open(file_path, 'rb') as f:
            processed: ProcessedVideo = pickle.load(f)

        frame_generator = processed.consume_frames(terminal)
        frame_rate = processed.framerate
        frame_amount = len(processed.frames)
    else:
        frame_generator = processor.process_video(file_path, ascii_mode, size)
        frame_rate = get_framerate(file_path)
        frame_amount = get_frame_amount(file_path)

    frame_time = 1.0 / frame_rate

    # processed = ProcessedVideo(frame_rate, size, ascii_mode, [frame[0] for frame in frame_generator])

    # frame_generator = processed.consume_frames(terminal)

    # audio_player = prepare_audio(file_path, frame_rate)
    # audio_player.start()  # Start the audio stream

    ansi_string = ""
    size_changed = False

    while True:
        frame_start = time.time()

        # audio_player.play_chunk(frame_idx) # Disabled at the moment due to technical issues

        if ansi_string and size_changed:
            terminal_api.clear_and_print_at(terminal, (0, 0), ansi_string)
        elif ansi_string:
            terminal_api.print_at(terminal, (0, 0), ansi_string)

        output = next(frame_generator, None)

        if output is None:
            break

        diff_buffer, size_changed = output

        ansi_string = processor.diff_buffer_to_ANSI(diff_buffer, terminal)

        elapsed = time.time() - frame_start
        sleep_time = max(0, frame_time - elapsed)

        actual_frame_time = elapsed + sleep_time
        actual_fps = 1.0 / actual_frame_time if actual_frame_time > 0 else 0.0
        playback_speed = actual_fps / frame_rate if frame_rate > 0 else 0.0

        if debug_mode and daemon_helper.daemon_manager:
            daemon_helper.daemon_manager.update_daemon(
                frames_shown=frame_idx,
                total_frames=frame_amount,
                idle_time_per_frame=sleep_time,
                data_throughput=len(ansi_string.encode('utf-8')) / 1024,
                playback_speed=playback_speed
            )
        
        frame_idx += 1
        await asyncio.sleep(sleep_time)

def play_video(file_path: str, ascii_mode: bool = False, size: int = 32, debug_mode: bool = False):
    # global audio_player
    
    terminal_api.clear_screen(terminal)
    terminal_api.hide_cursor(terminal)
    
    if debug_mode:
        daemon_helper.start_daemon()
    else:
        logging.getLogger().setLevel(logging.ERROR)
    
    try:    
        asyncio.run(_play_video(file_path, ascii_mode, size, debug_mode))
    except Exception as e:
        terminal_api.reset_text_color(terminal)
        terminal_api.clear_screen(terminal)
        terminal_api.show_cursor(terminal)
        raise Exception(f"An error occurred: {e}")
    
    terminal_api.reset_text_color(terminal)
    terminal_api.clear_screen(terminal)
    terminal_api.show_cursor(terminal)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Play a video in the terminal.")
    parser.add_argument("file_path", help="The path to the video file.")
    parser.add_argument("--size", type=int, default=32, help="The size of the video element.")
    parser.add_argument("--ascii", action="store_true", help="Render video as ASCII.")
    parser.add_argument("--debug", action="store_true", help="Open debug terminal and run with profiler.")
    args = parser.parse_args()

    if args.debug:
        cProfile.run('play_video(args.file_path, args.ascii, args.size, args.debug)')
    else:
        play_video(args.file_path, args.ascii, args.size, args.debug)
