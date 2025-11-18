from dataclasses import dataclass, field

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
    color_background: Color | None = None

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