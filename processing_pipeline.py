from blessed import Terminal

from video_processing import get_aspect_ratio, stream_video_from_disk
from ascii_tools import img_to_pixel_matrix
from data import Size, FrameBuffer, DiffBuffer
from constants import WIDTH_COMPENSATION
from diff_to_ansi import diff_buffer_to_ANSI

class VideoProcessor:
    def __init__(self):
        self.terminal = Terminal()
        self.term_width, self.term_height = self.terminal.width, self.terminal.height

    def diff_buffer_to_ANSI(self, diff_buffer: DiffBuffer, terminal: Terminal) -> str:
        return diff_buffer_to_ANSI(diff_buffer, terminal)

    def process_video(self, file_path: str, as_ascii: bool = False, size: int = 32) -> iter:
        generator = stream_video_from_disk(file_path)

        # frame_amount = get_frame_amount(file_path)
        # framerate = get_framerate(file_path)
        aspect_ratio = get_aspect_ratio(file_path)

        last_buffer = FrameBuffer()

        for frame in generator:
            matrix = img_to_pixel_matrix(
                frame,
                size=Size(
                    height=size,
                    width=int(size * WIDTH_COMPENSATION)
                ),
                render_as_ascii=as_ascii,
                aspect_ratio=aspect_ratio
            )

            buffer = FrameBuffer()
            buffer.write(matrix)

            output = buffer.get_difference(last_buffer, self.terminal) if self.terminal.width == self.term_width and self.terminal.height == self.term_height else buffer.get_difference(FrameBuffer(), self.terminal)

            size_changed = self.terminal.width != self.term_width or self.terminal.height != self.term_height

            self.term_width, self.term_height = self.terminal.width, self.terminal.height

            last_buffer = buffer

            yield (output, size_changed)
