import argparse
import cProfile
import asyncio
import logging
import time
import os

from blessed import Terminal

import pyximport
pyximport.install()

import terminal_api
import daemon_helper
import video_decoder

terminal = Terminal()

if os.name == 'nt':
    os.system('chcp 65001 >nul')

def _play_video(file_path: str, size: int = 32, debug_mode: bool = False):
    decoder = video_decoder.VideoDecoder(
        file_path,
        size
    )

    diff_generator = decoder.diff_frame_generator()

    frame_rate = decoder.get_frame_rate()
    frame_amount = decoder.get_total_frames()
    frame_time = 1.0 / frame_rate

    for frame_idx, frame in enumerate(diff_generator):
        frame_start = time.time()

        terminal_api.print_at_bytes((0, 0), frame)

        elapsed = time.time() - frame_start
        sleep_time = max(0, frame_time - elapsed)

        actual_frame_time = elapsed + sleep_time
        actual_fps = 1.0 / actual_frame_time if actual_frame_time > 0 else 0.0
        playback_speed = actual_fps / frame_rate if frame_rate > 0 else 0.0

        if debug_mode and daemon_helper.daemon_manager:
            daemon_helper.daemon_manager.update_daemon(
                frames_shown=frame_idx,
                total_frames=frame_amount,
                frames_buffered=decoder.get_buffered_frame_count(),
                data_throughput=len(frame) / 1024,
                playback_speed=playback_speed
            )
        
        time.sleep(sleep_time)

def play_video(file_path: str, size: int = 32, debug_mode: bool = False):
    terminal_api.clear_screen(terminal)
    terminal_api.hide_cursor()
    
    if debug_mode:
        daemon_helper.start_daemon()
    else:
        logging.getLogger().setLevel(logging.ERROR)
    
    try:    
        _play_video(file_path, size, debug_mode)

    except KeyboardInterrupt:
        pass

    except Exception as e:
        terminal_api.clear_screen(terminal)
        terminal_api.reset_text_color(terminal)
        terminal_api.show_cursor()
        raise Exception(f"\nAn error occurred: {e}")
    finally:
        # Always restore terminal state, even if interrupted or exception occurred
        terminal_api.reset_text_color(terminal)
        terminal_api.show_cursor()

    # Avoid clearing the error message
    terminal_api.clear_screen(terminal)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Play a video in the terminal.")
    parser.add_argument("file_path", help="The path to the video file.")
    parser.add_argument("--size", type=int, default=32, help="The size of the video element.")
    parser.add_argument("--debug", action="store_true", help="Open debug terminal and run with profiler.")
    args = parser.parse_args()

    if args.debug:
        cProfile.run('play_video(args.file_path, args.size, args.debug)')
    else:
        play_video(args.file_path, args.size, args.debug)
