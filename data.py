from dataclasses import dataclass, field
import abc

from blessed import Terminal

import pyximport
pyximport.install()
from diff_buffer import compute_diff_buffer

@dataclass
class Color:
    r: float
    g: float
    b: float

    def to_tuple_rgb(self) -> tuple[float, float, float]:
        return (self.r, self.g, self.b)
    
@dataclass
class Position:
    x: int
    y: int

@dataclass
class Size:
    width: int
    height: int

@dataclass
class Transform:
    position: Position
    size: Size

@dataclass
class Pixel:
    char: str
    color: Color
    position: Position

    @classmethod
    def string_to_pixels(cls, s: str, color: Color, position: Position) -> list['Pixel']:
        data = []
        for i, char in enumerate(s):
            data.append(Pixel(char=char, color=color, position=Position(position.x + i, position.y)))

        return data

class FrameBuffer:
    def __init__(self, size: Size = Size(0, 0)):
        self._buffer: list[Pixel] = [[]]
        self.grow_to_fit(size)

    def write(self, pixels: list[Pixel]) -> list[Position]:
        """
        Writes the given pixels to the buffer, expanding it as necessary.
        Returns a list of positions that were overwritten due to conflicting data.
        """
        overwritten_positions: list[Position] = []

        self.grow_to_fit(pixels[-1].position)

        for pixel in pixels:
            if self._buffer[pixel.position.y][pixel.position.x] is not None:
                overwritten_positions.append(pixel.position)

            self._buffer[pixel.position.y][pixel.position.x] = pixel

        return overwritten_positions

    def grow_to_fit(self, size: Size | Position) -> None:
        """
        Fills the buffer with empty entries to fit the required size.
        """
        width = 0
        height = 0

        if isinstance(size, Position):
            width = size.x + 1
            height = size.y + 1
        else:
            width = size.width + 1
            height = size.height + 1

        # Grow height if needed
        if height > len(self._buffer):
            self._buffer.extend([[] for _ in range(height - len(self._buffer))])

        # Grow width for each row (only if needed)
        for row in self._buffer:
            if width > len(row):
                row.extend([None] * (width - len(row)))

    def get_difference(self, other: 'FrameBuffer', terminal: Terminal, color_threshold: float = 0.05, render_outside_bounds: bool = False) -> 'DiffBuffer':
        """
        Computes which pixels differ between this buffer and another buffer,
        """

        return DiffBuffer(
            compute_diff_buffer(
                self._buffer,
                other._buffer,
                terminal.width,
                terminal.height,
                color_threshold,
                render_outside_bounds
            )
        )
    
    def apply_diff_buffer(self, diff_buffer: 'DiffBuffer') -> None:
        """
        Applies the given diff buffer to this frame buffer.
        """
        for position, pixel in diff_buffer.buffer:
            try:
                self._buffer[position.y][position.x] = pixel
            except IndexError:
                raise IndexError(f"Position {position} is out of bounds for ${len(self._buffer[0])}x{len(self._buffer)} frame buffer.")

    def asDiffBuffer(self) -> 'DiffBuffer':
        """
        Converts the entire frame buffer into a diff buffer.
        """
        diffs: list[tuple[Position, Pixel]] = []

        for y, row in enumerate(self._buffer):
            for x, pixel in enumerate(row):
                if pixel is not None:
                    diffs.append((Position(x, y), pixel))

        return DiffBuffer(diffs)

class DiffBuffer:
    def __init__(self, diffs: list[tuple[Position, Pixel]]):
        self.buffer = diffs

@dataclass
class DaemonMessage:
    """Message sent from main application to daemon terminal"""
    frames_shown: int
    total_frames: int
    idle_time_per_frame: float
    data_throughput: float
    playback_speed: float

@dataclass
class ProcessedVideo:
    framerate: int
    size: int
    is_in_ascii: bool
    frames: list[DiffBuffer] = field(default_factory=list)
    
    _current_buffer: FrameBuffer = field(init=False)
    _term_width: int = field(init=False, default=-1)
    _term_height: int = field(init=False, default=-1)

    def consume_frames(self, terminal: Terminal) -> iter:
        first_frame = self.frames[0]
        max_x = max(pos.x for pos, _ in first_frame.buffer) if first_frame.buffer else 0
        max_y = max(pos.y for pos, _ in first_frame.buffer) if first_frame.buffer else 0

        self._current_buffer = FrameBuffer(size=Size(max_x, max_y))

        for diff in self.frames:
            self._current_buffer.apply_diff_buffer(diff)
            if self._term_width != terminal.width or self._term_height != terminal.height:
                self._term_width = terminal.width
                self._term_height = terminal.height
                size_changed = True

                yield (self._current_buffer.asDiffBuffer(), size_changed)
            else:
                size_changed = False

                yield (diff, size_changed)