import argparse
import cProfile
import logging
import time
import os

from blessed import Terminal
from ffpyplayer.player import MediaPlayer

import terminal_api
import daemon_helper
import video_decoder
import ffmpeg

terminal = Terminal()

if os.name == 'nt':
    os.system('chcp 65001 >nul')

def _play_video(file_path: str, size: int = 32, debug_mode: bool = False, muted: bool = False, compression: int = 150):
    decoder = video_decoder.VideoDecoder(
        file_path,
        size,
        compression
    )
    
    probe = ffmpeg.probe(file_path)
    audio_streams = [stream for stream in probe['streams'] if stream['codec_type'] == 'audio']
    
    muted = not (len(audio_streams) > 0 and not muted)

    player = None
    if not muted:
        player = MediaPlayer(file_path, ff_opts={'vn': True, 'sn': True}, loglevel='quiet')

    diff_generator = decoder.diff_frame_generator()

    frame_rate = decoder.get_frame_rate()
    frame_amount = decoder.get_total_frames()
    frame_time = 1.0 / frame_rate
    
    # Track pause state to avoid spamming the player
    is_paused = False

    # Start the generator
    try:
        frame = next(diff_generator)
    except StopIteration:
        if player:
            player.close_player()
        return

    frame_idx = 0
    
    # Track start time for wall-clock fallback
    # Moved here so we don't count the time it took to load the first frame as "lag"
    start_time = time.time()

    try:
        while True:
            frame_start_time = time.time()

            # Render the current frame
            terminal_api.print_at_bytes((0, 0), frame)

            # Get next frame immediately. This includes decoding time.
            try:
                frame = diff_generator.send(True)
                frame_idx += 1
            except StopIteration:
                break

            # Sync Logic
            video_pts = frame_idx * frame_time
            audio_pts = player.get_pts() if player else None

            if audio_pts is not None:
                drift = video_pts - audio_pts
                
                if drift > 0.005:
                    # Video is faster than audio. Sleep to sync.
                    # Only sleep if drift is significant to avoid OS sleep granularity issues
                    time.sleep(drift)
                    if is_paused:
                        player.set_pause(False)
                        is_paused = False
                elif drift < -0.2:
                    # Video is slower than audio by > 200ms. Pause audio to let video catch up.
                    if not is_paused:
                        player.set_pause(True)
                        is_paused = True
                else:
                    # Video is slightly behind or in sync. Ensure audio plays.
                    if is_paused:
                        player.set_pause(False)
                        is_paused = False
            else:
                # Fallback: Audio not ready yet or finished. Sync to wall clock.
                target_time = start_time + (frame_idx * frame_time)
                current_time = time.time()
                sleep_time = target_time - current_time
                if sleep_time > 0.005:
                    time.sleep(sleep_time)
                elif sleep_time < -0.2:
                    # We are behind by more than 200ms. 
                    # Instead of fast-forwarding to catch up, we reset the timeline.
                    # This effectively "drops" the time we lost.
                    start_time = current_time - (frame_idx * frame_time)

            if debug_mode and daemon_helper.daemon_manager:
                frame_end_time = time.time()
                # Calculate stats
                daemon_helper.daemon_manager.update_daemon(
                    frames_shown=frame_idx,
                    total_frames=frame_amount,
                    frames_buffered=decoder.get_buffered_frame_count(),
                    data_throughput=len(frame) / 1024,
                    playback_speed= 1.0 / (frame_end_time - frame_start_time) / frame_rate
                )
    finally:
        # Mute immediately to stop any buffered audio from playing
        if player:
            player.set_volume(0.0)
            player.set_pause(True)
            player.close_player()

def play_video(file_path: str, size: int = 32, debug_mode: bool = False, muted: bool = False, compression: int = 150):
    terminal_api.clear_screen(terminal)
    terminal_api.hide_cursor()
    
    if debug_mode:
        daemon_helper.start_daemon()
    else:
        logging.getLogger().setLevel(logging.ERROR)
    
    try:    
        _play_video(file_path, size, debug_mode, muted, compression)

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
    parser.add_argument("--muted", action="store_true", help="Mute the audio.")
    parser.add_argument("--compression", type=int, default=150, help="The threshold for color change detection (default: 150).")
    args = parser.parse_args()

    if args.debug:
        cProfile.run('play_video(args.file_path, args.size, args.debug, args.muted, args.compression)')
    else:
        play_video(args.file_path, args.size, args.debug, args.muted, args.compression)
