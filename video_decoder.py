import cv2
import numpy as np
import multiprocessing
from multiprocessing import shared_memory
import time
from terminal_api import get_move_sequence_bytes
from constants import PERCEPTUAL_WEIGHT_BLUE, PERCEPTUAL_WEIGHT_GREEN, PERCEPTUAL_WEIGHT_RED, COLOR_CHANGE_THRESHOLD

# Pre-encode the block character to avoid doing it millions of times
BLOCK_CHAR = '▀'.encode('utf-8')

def _video_producer_process(file_path: str, resolution: int, 
                          shm_name: str, buffer_size: int, 
                          free_queue: multiprocessing.Queue, ready_queue: multiprocessing.Queue):
    """
    Standalone function to run in a separate process.
    Decodes video and puts byte sequences into shared memory.
    """
    # Attach to the existing shared memory block
    shm = shared_memory.SharedMemory(name=shm_name)

    # The process must open its own file handle; handles cannot be pickled across processes
    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        ready_queue.put(None)
        shm.close()
        return

    original_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    original_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    aspect_ratio = original_width / original_height
    frame_height = resolution
    frame_width = int(frame_height * aspect_ratio)

    # Pre-compute move sequences for this resolution
    # This avoids lru_cache hashing overhead and function calls inside the loop
    # move_sequences[y][x]
    # We use h // 2 because we are rendering blocks (2 pixels high)
    rows_count = frame_height // 2
    move_sequences = [
        [get_move_sequence_bytes((x, y)) for x in range(frame_width)]
        for y in range(rows_count + 1) # +1 buffer just in case
    ]

    # Perceptual weights for BGR: Blue, Green, Red
    # This matches human eye perception (Luma) to prioritize Green/Brightness changes
    # and ignore subtle Blue/Red noise.
    perceptual_weights = np.array([PERCEPTUAL_WEIGHT_BLUE, PERCEPTUAL_WEIGHT_GREEN, PERCEPTUAL_WEIGHT_RED], dtype=np.int16)

    prev_blocks = None

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Resize frame to target resolution
            # INTER_LINEAR is faster than INTER_AREA
            frame = cv2.resize(frame, (frame_width, frame_height), interpolation=cv2.INTER_LINEAR)

            # Reshape into blocks: (Rows//2, 2_vertical_pixels, Columns, 3_colors)
            h, w, c = frame.shape
            # Cast to int16 immediately to avoid repeated casting during diff and allow negative subtraction
            blocks = frame.reshape(h // 2, 2, w, c).astype(np.int16)

            if prev_blocks is None:
                # Force full redraw for the first frame
                change_mask = np.ones((h // 2, w), dtype=bool)
                prev_blocks = blocks.copy()
            else:
                # Weighted Euclidean-ish Distance (Manhattan on weighted channels)
                diff_vals = np.abs(blocks - prev_blocks)
                weighted_diff = diff_vals * perceptual_weights
                diff_score = np.sum(weighted_diff, axis=(1, 3))
                
                change_mask = diff_score > COLOR_CHANGE_THRESHOLD

                # Update the 'prev_blocks' state only for pixels that changed
                prev_blocks = np.where(change_mask[:, None, :, None], blocks, prev_blocks)

            rows, cols = np.where(change_mask)

            buffer = bytearray()

            if len(rows) > 0:
                changed_colors = blocks[rows, :, cols, :]
                top_colors = changed_colors[:, 0, ::-1] 
                bot_colors = changed_colors[:, 1, ::-1]

                # Optimization: Vectorized check for solid blocks (Top Color == Bottom Color)
                # This moves the comparison out of the slow Python loop
                is_solid = np.all(top_colors == bot_colors, axis=1)

                # Force int32 to avoid float conversions and ensure fast Python int access
                update_data = np.column_stack((
                    cols, rows, 
                    top_colors, bot_colors,
                    is_solid # Add boolean flag as integer (0 or 1)
                )).astype(np.int32)

                # Optimization: REMOVED np.lexsort
                # np.where already returns indices sorted by Row (y), then Column (x).
                # Sorting again was redundant and expensive.
                
                # Convert to list for faster iteration in Python
                updates_list = update_data.tolist()

                # Initialize prev_y to -1 to detect the start of the frame
                prev_y = -1
                prev_x = -1
                
                # Optimization: Track previous color to avoid redundant ANSI codes
                prev_r, prev_g, prev_b = -1, -1, -1
                prev_r2, prev_g2, prev_b2 = -1, -1, -1
                
                # Local variable caching for speed
                _extend = buffer.extend
                _block_char = BLOCK_CHAR
                _space_char = b' '
                _newline_seq = b'\r\n'
                
                # Split format strings to allow independent updates
                _fg_fmt = b'\x1b[38;2;%d;%d;%dm'
                _bg_fmt = b'\x1b[48;2;%d;%d;%dm'

                for row in updates_list:
                    x, y = row[0], row[1]
                    
                    # Optimization: Efficient Moves
                    # Added y > 0 check to prevent newline at (0,0) when starting from -1.
                    # This forces an absolute move for the first line, ensuring correct alignment.
                    if y == prev_y + 1 and x == 0 and y > 0:
                        # If we are starting a new line at x=0, just send a newline (2 bytes)
                        _extend(_newline_seq)
                    elif y != prev_y or x != prev_x + 1:
                        # Otherwise, use absolute positioning
                        _extend(move_sequences[y][x])
                    
                    r, g, b = row[2], row[3], row[4]
                    r2, g2, b2 = row[5], row[6], row[7]
                    solid_block = row[8] # Retrieved from vectorized check

                    # Optimization: Solid Block Detection
                    if solid_block:
                        if (r2 != prev_r2 or g2 != prev_g2 or b2 != prev_b2):
                            _extend(_bg_fmt % (r2, g2, b2))
                            prev_r2, prev_g2, prev_b2 = r2, g2, b2
                        _extend(_space_char)
                    else:
                        # Normal Half-Block
                        if (r != prev_r or g != prev_g or b != prev_b):
                            _extend(_fg_fmt % (r, g, b))
                            prev_r, prev_g, prev_b = r, g, b
                        
                        if (r2 != prev_r2 or g2 != prev_g2 or b2 != prev_b2):
                            _extend(_bg_fmt % (r2, g2, b2))
                            prev_r2, prev_g2, prev_b2 = r2, g2, b2
                        
                        _extend(_block_char)
                    
                    prev_x = x
                    prev_y = y
            
            # --- Shared Memory Transfer ---
            # Handle data larger than buffer size by chunking (though 64MB should be enough)
            total_len = len(buffer)
            sent_len = 0
            
            while sent_len < total_len or total_len == 0:
                # Get a free buffer index (blocks if full)
                idx = free_queue.get()
                if idx is None: # Sentinel received
                    break
                
                chunk_size = min(total_len - sent_len, buffer_size)
                
                if chunk_size > 0:
                    offset = idx * buffer_size
                    # Direct memory copy into shared buffer
                    shm.buf[offset:offset+chunk_size] = buffer[sent_len:sent_len+chunk_size]
                
                # Notify consumer that data is ready
                # We send the chunk size. If it's a partial frame, the consumer just prints it.
                # Note: This might cause slight tearing if the consumer sleeps between chunks, 
                # but with 64MB buffer, this loop usually runs only once.
                ready_queue.put((idx, chunk_size))
                
                sent_len += chunk_size
                
                # If total_len was 0 (empty frame), we sent one empty update and break
                if total_len == 0:
                    break

    except Exception:
        pass
    finally:
        cap.release()
        ready_queue.put(None) # Signal EOF
        shm.close()

class VideoDecoder:
    def __init__(self, file_path: str, resolution: int):
        self.file_path = file_path
        self.resolution = resolution if resolution % 2 == 0 else resolution + 1
        
        # Open briefly to get metadata, then release.
        # The worker process will open its own handle.
        self.cap = cv2.VideoCapture(self.file_path)
        self.frame_rate = self.cap.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.cap.release() 
        
        self.ready_queue = None
        self.producer_process = None
        self.shm = None

    def get_frame_rate(self) -> float:
        return self.frame_rate
    
    def get_total_frames(self) -> int:
        return self.total_frames

    def get_buffered_frame_count(self) -> int:
        if self.ready_queue:
            try:
                return self.ready_queue.qsize()
            except:
                return 0
        return 0

    def diff_frame_generator(self):
        # Allocate 64MB per frame buffer to handle full HD redraws without truncation
        # 1920x1080 / 2 blocks * ~40 bytes/block ~= 40MB. 64MB is safe.
        BUFFER_SIZE = 64 * 1024 * 1024 
        NUM_BUFFERS = 4 # Ring buffer size
        
        # Create shared memory block
        self.shm = shared_memory.SharedMemory(create=True, size=BUFFER_SIZE * NUM_BUFFERS)
        
        free_queue = multiprocessing.Queue()
        self.ready_queue = multiprocessing.Queue()
        
        # Initialize free queue with all buffer indices
        for i in range(NUM_BUFFERS):
            free_queue.put(i)
            
        self.producer_process = multiprocessing.Process(
            target=_video_producer_process,
            args=(self.file_path, self.resolution, 
                  self.shm.name, BUFFER_SIZE, 
                  free_queue, self.ready_queue),
            daemon=True
        )
        self.producer_process.start()

        try:
            while True:
                item = self.ready_queue.get()
                if item is None:
                    break
                
                idx, size = item
                offset = idx * BUFFER_SIZE
                
                # Read directly from shared memory
                # bytes() creates a copy, which is safe as we are about to release the buffer
                data = bytes(self.shm.buf[offset:offset+size])
                
                # Return buffer index to the free queue so producer can reuse it
                free_queue.put(idx)
                
                yield data
        finally:
            # Cleanup resources
            if self.producer_process.is_alive():
                # Send sentinel to unblock producer if it's waiting
                free_queue.put(None)
                self.producer_process.join(timeout=1.0)
                if self.producer_process.is_alive():
                    self.producer_process.terminate()
            
            self.shm.close()
            self.shm.unlink() # Mark for deletion
