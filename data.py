from dataclasses import dataclass, field
import abc

from blessed import Terminal

import pyximport
pyximport.install()
from diff_buffer import compute_diff_buffer
import terminal_api

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
    def __init__(self):
        self._buffer: list[Pixel] = []

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

    def get_difference(self, other: 'FrameBuffer', terminal: Terminal, color_threshold: float = 0.05, render_outside_bounds: bool = False) -> str:
        """
        Returns a single string containing all terminal sequences to update the
        display from the other buffer to this one.
        """

        diff_buffer = compute_diff_buffer(
            self._buffer,
            other._buffer,
            terminal.width,
            terminal.height,
            color_threshold,
            render_outside_bounds
        )

        if not diff_buffer:
            return ""

        # Sort by y then x for more efficient drawing
        diff_buffer.sort(key=lambda p: (p[0][1], p[0][0]))

        output_parts = []
        
        # Use a non-existent color to ensure the first color is always set
        current_color = (-1.0, -1.0, -1.0) 
        # Use a non-existent position to ensure the first move is always made
        current_position = (-1, -1)

        for (x, y), pixel in diff_buffer:
            final_color = pixel.color.to_tuple_rgb()

            # If we need to move the cursor
            if (x, y) != current_position:
                # Don't move if it's just the next character on the same line
                if not (y == current_position[1] and x == current_position[0] + 1):
                    output_parts.append(terminal_api.get_move_sequence((x, y)))
            
            # Change color if different from the last one
            if final_color != current_color:
                output_parts.append(terminal.color_rgb(int(final_color[0] * 255), int(final_color[1] * 255), int(final_color[2] * 255)))
                current_color = final_color

            output_parts.append(pixel.char)
            current_position = (x, y)

        return "".join(output_parts)

@dataclass
class Element(abc.ABC):
    """
    Stores a matrix of Pixels and a couple of methods to manipulate them, as well as the
    corresponding logic to change the element's look.
    """
    priority: int = 0
    data: list[Pixel] = field(default_factory=list, init=False)

    @property
    @abc.abstractmethod
    def transform(self) -> Transform:
        pass

    @transform.setter
    @abc.abstractmethod
    def transform(self, value: Transform):
        pass

    @abc.abstractmethod
    def on_terminal_size_change(self, new_size: Size) -> None:
        """
        Recalculate the data here if necessary.
        """
        pass

    @abc.abstractmethod
    def on_new_frame(self) -> None:
        """
        Called when a new frame is being rendered.
        """
        pass

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
    frames: list[str]

    def consume_frames(self) -> iter:
        for frame in self.frames:
            yield frame
