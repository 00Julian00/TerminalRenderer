"""
Audio player module for synchronized video playback.

This module handles audio extraction from video files and frame-synchronized
playback, ensuring audio stays in sync even with inconsistent frame times.
"""

import numpy as np
import sounddevice as sd
from pydub import AudioSegment


class AudioPlayer:
    """
    Frame-synchronized audio player that plays audio chunks in sync with video frames.
    
    Uses direct write mode (not callback) so audio playback is controlled by
    the video rendering loop, ensuring perfect synchronization.
    """
    
    def __init__(self, sample_rate: int, samples_per_frame: int, audio_chunks: list):
        """
        Initialize the audio player.
        
        Args:
            sample_rate: Audio sample rate (e.g., 44100, 48000)
            samples_per_frame: Number of audio samples per video frame
            audio_chunks: List of pre-split audio chunks, one per frame
        """
        self.sample_rate = sample_rate
        self.samples_per_frame = samples_per_frame
        self.audio_chunks = audio_chunks
        self.stream = None
        self.finished = False
    
    def start(self):
        """Start the audio output stream in write mode (no callback)."""
        self.stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=1,
            blocksize=self.samples_per_frame
        )
        self.stream.start()
    
    def play_chunk(self, frame_idx: int):
        """
        Play audio chunk for this frame (non-blocking write).
        
        Args:
            frame_idx: The index of the video frame being displayed
        """
        if frame_idx < len(self.audio_chunks):
            chunk = self.audio_chunks[frame_idx]
            # Reshape for sounddevice (needs to be 2D: samples x channels)
            chunk_2d = chunk.reshape(-1, 1)
            self.stream.write(chunk_2d)
    
    def stop(self):
        """Stop and close the audio output stream."""
        self.finished = True
        if self.stream:
            self.stream.stop()
            self.stream.close()


def prepare_audio(file_path: str, framerate: float) -> AudioPlayer:
    """
    Prepare audio data from a video file for frame-synchronized playback.
    
    This function:
    1. Extracts audio from the video file
    2. Normalizes the audio data
    3. Converts stereo to mono
    4. Splits audio into chunks aligned with video frames
    5. Returns an AudioPlayer ready for playback
    
    Args:
        file_path: Path to the video file
        framerate: Video framerate (frames per second)
        
    Returns:
        AudioPlayer: An initialized audio player ready to use
        
    Example:
        >>> player = prepare_audio("video.mp4", 30.0)
        >>> player.start()
        >>> for frame_idx in range(num_frames):
        ...     player.play_chunk(frame_idx)
        ...     # ... render video frame ...
        >>> player.stop()
    """
    # Load audio from video file
    audio = AudioSegment.from_file(file_path)
    audio_data = np.array(audio.get_array_of_samples(), dtype=np.float32)
    
    # Normalize based on sample width
    if audio.sample_width == 2:  # 16-bit audio
        audio_data = audio_data / 32768.0
    elif audio.sample_width == 1:  # 8-bit audio
        audio_data = (audio_data - 128) / 128.0
    elif audio.sample_width == 4:  # 32-bit audio
        audio_data = audio_data / 2147483648.0
    
    # Convert stereo to mono
    if audio.channels == 2:
        audio_data = audio_data.reshape((-1, 2))  # Reshape for stereo
        audio_data = audio_data.mean(axis=1)  # Convert to mono
    
    sample_rate = audio.frame_rate
    
    # Calculate samples per frame
    samples_per_frame = int(sample_rate / framerate)
    
    # Split audio into frame-aligned chunks
    audio_chunks = []
    total_samples = len(audio_data)
    frame_idx = 0
    
    while True:
        start_sample = frame_idx * samples_per_frame
        end_sample = start_sample + samples_per_frame
        
        if start_sample >= total_samples:
            break
            
        chunk = audio_data[start_sample:end_sample]
        audio_chunks.append(chunk)
        frame_idx += 1
    
    # Create and return the audio player
    return AudioPlayer(sample_rate, samples_per_frame, audio_chunks)