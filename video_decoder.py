import struct

from data import DiffBuffer, Pixel, Position, Color

import zstandard as zstd

# Command byte flags (same as encoder)
CMD_COORDS = 0x01
CMD_RGB = 0x02
CMD_BG = 0x04
CMD_CHAR = 0x08
CMD_RLE = 0x10

class VideoDecoder:
    def __init__(self, filename: str):
        decompressor = zstd.ZstdDecompressor()

        with open(filename, 'rb') as f:
            compressed = f.read()
            
        self._data = decompressor.decompress(compressed)
        
        self._offset = 0
        self.framerate = None
        self.total_frames = None
        self._last_position = None
        self._last_fg_color = None
        self._last_bg_color = None
        self._last_char = None
        self._frame_count = 0
        
        # Read metadata header
        self._read_header()

    @staticmethod
    def from_bytes(data: bytes) -> 'VideoDecoder':
        """Create a VideoDecoder from raw bytes."""
        decoder = VideoDecoder.__new__(VideoDecoder)
        decoder._data = data
        decoder._offset = 0
        decoder.framerate = None
        decoder.total_frames = None
        decoder._last_position = None
        decoder._last_fg_color = None
        decoder._last_bg_color = None
        decoder._last_char = None
        decoder._frame_count = 0
        
        decoder._read_header()
        return decoder

    def consume_frames(self) -> iter:
        """Generator that yields decoded frames as DiffBuffers."""
        while self.has_frames():
            yield self.decode_next_frame()
    
    def _read_header(self):
        """Read framerate and total frame count from header."""
        self.framerate = struct.unpack_from('I', self._data, self._offset)[0]
        self._offset += 4
        self.total_frames = struct.unpack_from('I', self._data, self._offset)[0]
        self._offset += 4
    
    def get_framerate(self) -> int:
        """Get the video framerate."""
        return self.framerate
    
    def get_total_frames(self) -> int:
        """Get the total number of frames in the video."""
        return self.total_frames
    
    def _read_bytes(self, n: int) -> bytes:
        """Consume n bytes from the buffer."""
        if self._offset + n > len(self._data):
            raise EOFError("Unexpected end of video data")
        
        data = self._data[self._offset:self._offset + n]
        self._offset += n
        return data
    
    def _read_byte(self) -> int:
        """Consume a single byte."""
        return self._read_bytes(1)[0]
    
    def has_frames(self) -> bool:
        """Check if there are more frames to decode."""
        return self._offset < len(self._data)
    
    def decode_next_frame(self) -> DiffBuffer | None:
        """Decode and return the next frame's diff buffer."""
        if not self.has_frames():
            return None
        
        # Only reset state on first frame (to match encoder behavior)
        if self._frame_count == 0:
            self._last_position = None
            self._last_fg_color = None
            self._last_bg_color = None
            self._last_char = None
        
        # Read frame length
        frame_length = struct.unpack_from('I', self._data, self._offset)[0]
        self._offset += 4
        
        frame_end = self._offset + frame_length
        diffs = []
        
        # Decode pixels until end of frame
        while self._offset < frame_end:
            pixels = self._decode_pixel()
            diffs.extend(pixels)
        
        self._frame_count += 1
        
        return DiffBuffer(diffs)
    
    def _decode_pixel(self) -> list[tuple[Position, Pixel]]:
        """Decode a single pixel (or run of pixels) and return as list."""
        cmd = self._read_byte()
        
        # Read coordinates if present
        if cmd & CMD_COORDS:
            x, y = struct.unpack('hh', self._read_bytes(4))
            position = Position(x, y)
        else:
            # Sequential - increment from last position
            if self._last_position is None:
                raise ValueError("No coordinates provided for first pixel")
            position = Position(self._last_position.x + 1, self._last_position.y)
        
        # Read foreground color if present
        if cmd & CMD_RGB:
            r, g, b = self._read_bytes(3)
            self._last_fg_color = Color(r / 255.0, g / 255.0, b / 255.0)

        if self._last_fg_color is None:
            raise ValueError("No foreground color available")

        # Read background color if present
        bg_color = None
        if cmd & CMD_BG:
            r, g, b = self._read_bytes(3)
            self._last_bg_color = Color(r / 255.0, g / 255.0, b / 255.0)
            bg_color = self._last_bg_color
        elif self._last_bg_color is not None:
            bg_color = self._last_bg_color
        
        # Read character if present
        if cmd & CMD_CHAR:
            char_len = self._read_byte()
            char_bytes = self._read_bytes(char_len)
            self._last_char = char_bytes.decode('utf-8')
        
        if self._last_char is None:
            raise ValueError("No character available")
        
        # Read run length if present
        run_length = 1
        if cmd & CMD_RLE:
            run_length = struct.unpack('H', self._read_bytes(2))[0]
        
        # Create pixels for the run
        result = []
        for i in range(run_length):
            pos = Position(position.x + i, position.y)
            pixel = Pixel(
                char=self._last_char,
                color=self._last_fg_color,
                position=pos,
                color_background=bg_color
            )
            result.append((pos, pixel))
        
        # Update last position
        self._last_position = Position(position.x + run_length - 1, position.y)
        
        return result