import argparse
import cProfile
import asyncio
import logging
import time

from blessed import Terminal

import data
import terminal_api
from processing_pipeline import VideoProcessor
import daemon_helper
import video_decoder
import video_encoder
import video_processing
# from audio_player import prepare_audio, AudioPlayer

terminal = Terminal()

processor = VideoProcessor()

# audio_player: AudioPlayer = None

async def _play_video(file_path: str, ascii_mode: bool = False, size: int = 32, debug_mode: bool = False):
    frame_idx = 0

    if not ascii_mode:
        size *= 2 # Keep scaling consistent between ASCII and normal mode

    if (file_path.lower().endswith('.ctv')):
        processed = video_decoder.VideoDecoder(file_path)
        frame_amount = processed.get_total_frames()
    else:
        frame_amount = video_processing.get_frame_amount(file_path)
        encoder = video_encoder.VideoEncoder(framerate=video_processing.get_framerate(file_path))
        frame_generator = processor.process_video(file_path, ascii_mode, size, batch_size=16)

        encoder.encode_all(frame_generator)

        processed = video_decoder.VideoDecoder.from_bytes(
            encoder.get_data()
        )

    frame_generator = processed.consume_frames()

    frame_rate = processed.framerate

    frame_time = 1.0 / frame_rate

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

        # diff_buffer, size_changed = output
        diff_buffer = output

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
    terminal_api.hide_cursor()
    
    if debug_mode:
        daemon_helper.start_daemon()
    else:
        logging.getLogger().setLevel(logging.ERROR)
    
    try:    
        asyncio.run(_play_video(file_path, ascii_mode, size, debug_mode))

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
    parser.add_argument("--ascii", action="store_true", help="Render video as ASCII.")
    parser.add_argument("--debug", action="store_true", help="Open debug terminal and run with profiler.")
    args = parser.parse_args()

    if args.debug:
        cProfile.run('play_video(args.file_path, args.ascii, args.size, args.debug)')
    else:
        play_video(args.file_path, args.ascii, args.size, args.debug)
