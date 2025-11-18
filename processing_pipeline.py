from blessed import Terminal
import queue
import threading

from data import Size, FrameBuffer, DiffBuffer
from video_processing import get_aspect_ratio, stream_video_from_disk
from pixel_matrix import img_to_pixel_matrix_batched
from constants import ASCII_MODE_COLOR_OFFSET_THRESHOLD, NORMAL_MODE_COLOR_OFFSET_THRESHOLD, WIDTH_COMPENSATION, WIDTH_COMPENSATION_ASCII
from diff_to_ansi import diff_buffer_to_ANSI

class VideoProcessor:
    def __init__(self):
        self.terminal = Terminal()
        self._frame_queue = queue.Queue(maxsize=120) # Limit queue size to prevent high memory usage
        self._matrix_queue = queue.Queue(maxsize=120) # Limit queue size
        self._frame_production_finished = False
        self._matrix_production_finished = False

    def diff_buffer_to_ANSI(self, diff_buffer: DiffBuffer, terminal: Terminal) -> str:
        return diff_buffer_to_ANSI(diff_buffer, terminal)
    
    def _frame_producer_thread(self, file_path: str):
        def produce_frames():
            for frame in stream_video_from_disk(file_path):
                self._frame_queue.put(frame)
            self._frame_production_finished = True

        thread = threading.Thread(target=produce_frames, daemon=True)
        thread.start()

    def _matrix_producer_thread(self, size: Size, as_ascii: bool, aspect_ratio: float, batch_size: int):
        def produce_matrices():
            while not self._frame_production_finished or not self._frame_queue.empty():
                frame_batch = []
                try:
                    # Non-blocking get to form a batch quickly
                    for _ in range(batch_size):
                        frame_batch.append(self._frame_queue.get_nowait())
                except queue.Empty:
                    if not frame_batch:
                        # If the queue was empty and we got no frames, wait a bit
                        # This prevents busy-waiting when frame production is slow
                        threading.Event().wait(0.01)
                        continue
                
                if not frame_batch:
                    continue

                matrices = img_to_pixel_matrix_batched(
                    frame_batch,
                    size=size,
                    render_as_ascii=as_ascii,
                    aspect_ratio=aspect_ratio
                )

                for matrix in matrices:
                    self._matrix_queue.put(matrix)
            
            self._matrix_production_finished = True

        thread = threading.Thread(target=produce_matrices, daemon=True)
        thread.start()

    def process_video(self, file_path: str, as_ascii: bool = False, size: int = 32, batch_size: int = 1) -> iter:
        aspect_ratio = get_aspect_ratio(file_path)
        last_buffer = FrameBuffer()

        self._frame_producer_thread(file_path)
        self._matrix_producer_thread(
            size=Size(
                height=size,
                width=int(size * (WIDTH_COMPENSATION_ASCII if as_ascii else WIDTH_COMPENSATION))
            ),
            as_ascii=as_ascii,
            aspect_ratio=aspect_ratio,
            batch_size=batch_size
        )

        while not self._matrix_production_finished or not self._matrix_queue.empty():
            try:
                matrix = self._matrix_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            buffer = FrameBuffer()
            
            buffer.write(matrix)

            color_threshold = NORMAL_MODE_COLOR_OFFSET_THRESHOLD if not as_ascii else ASCII_MODE_COLOR_OFFSET_THRESHOLD

            output = buffer.get_difference(last_buffer, self.terminal, color_threshold=color_threshold, render_outside_bounds=True)

            self.term_width, self.term_height = self.terminal.width, self.terminal.height

            last_buffer = buffer

            yield output
