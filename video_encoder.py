import struct

import zstandard as zstd

from data import DiffBuffer, Pixel, Position, Color

# Command byte flags
CMD_COORDS = 0x01   # Next 4 bytes are x,y coordinates (2x int16)
CMD_RGB = 0x02      # Next 3 bytes are foreground RGB
CMD_BG = 0x04       # Next 3 bytes are background RGB
CMD_CHAR = 0x08     # Next 1 byte is character
CMD_RLE = 0x10      # Next 2 bytes are repeat count (uint16)

class VideoEncoder:
    def __init__(self, framerate: int):
        self.framerate = framerate
        self._buffer = bytearray()
        self._last_position = None
        self._last_fg_color = None
        self._last_bg_color = None
        self._last_char = None
        self._frame_count = 0
        
        # Write metadata header:
        # 4 bytes: framerate
        # 4 bytes: total frame count (placeholder, updated on save)
        self._buffer.extend(struct.pack('I', framerate))
        self._buffer.extend(struct.pack('I', 0))  # Placeholder for frame count
    
    def encode_diff(self, diff: DiffBuffer):
        """Encode a diff buffer with run-length encoding."""
        # Frame length placeholder
        frame_start = len(self._buffer)
        self._buffer.extend(struct.pack('I', 0))  # Placeholder
        
        # Only reset tracking for the FIRST frame
        # For subsequent frames, we maintain state to enable proper diffing
        if self._frame_count == 0:
            self._last_position = None
            self._last_fg_color = None
            self._last_bg_color = None
            self._last_char = None
        
        # Group consecutive identical pixels for RLE
        i = 0
        while i < len(diff.buffer):
            position, pixel = diff.buffer[i]
            
            # Find run length - how many consecutive identical pixels?
            run_length = 1
            while (i + run_length < len(diff.buffer) and
                   run_length < 65535):  # uint16 max
                next_pos, next_pixel = diff.buffer[i + run_length]
                
                # Check if next pixel is sequential and identical
                expected_pos = Position(position.x + run_length, position.y)
                if (next_pos.x != expected_pos.x or 
                    next_pos.y != expected_pos.y or
                    not self._pixels_equal(pixel, next_pixel)):
                    break
                
                run_length += 1
            
            # Encode this run
            self._encode_pixel_run(position, pixel, run_length)
            i += run_length
        
        # Write actual frame length
        frame_length = len(self._buffer) - frame_start - 4
        struct.pack_into('I', self._buffer, frame_start, frame_length)
        
        self._frame_count += 1

    def encode_all(self, diffs: list[DiffBuffer]):
        """Encode a list of diff buffers as frames."""
        for diff in diffs:
            self.encode_diff(diff)

    def _finalize_header(self):
        """Update the frame count in the header."""
        struct.pack_into('I', self._buffer, 4, self._frame_count)

    def get_data(self) -> bytes:
        """Get the encoded video data as bytes."""
        self._finalize_header()
        return bytes(self._buffer)
    
    def _pixels_equal(self, p1: Pixel, p2: Pixel) -> bool:
        """Check if two pixels are identical."""
        if p1.char != p2.char:
            return False
        if not self._colors_equal(p1.color, p2.color):
            return False
        
        # Handle background color
        if (p1.color_background is None) != (p2.color_background is None):
            return False
        if p1.color_background is not None and p2.color_background is not None:
            if not self._colors_equal(p1.color_background, p2.color_background):
                return False
        
        return True
    
    def _colors_equal(self, c1: Color, c2: Color) -> bool:
        """Check if two colors are equal."""
        return c1.r == c2.r and c1.g == c2.g and c1.b == c2.b
    
    def _encode_pixel_run(self, position: Position, pixel: Pixel, run_length: int):
        """Encode a run of identical pixels."""
        cmd = 0
        
        # Check if we need coordinates
        needs_coords = (self._last_position is None or 
                       position.x != self._last_position.x + 1 or
                       position.y != self._last_position.y)
        
        if needs_coords:
            cmd |= CMD_COORDS
        
        # Check if foreground color changed
        if not self._colors_equal(pixel.color, self._last_fg_color) if self._last_fg_color else True:
            cmd |= CMD_RGB
        
        # Check if background color changed
        has_bg = pixel.color_background is not None
        bg_changed = False
        if has_bg:
            if self._last_bg_color is None or not self._colors_equal(pixel.color_background, self._last_bg_color):
                cmd |= CMD_BG
                bg_changed = True
        
        # Check if character changed
        if pixel.char != self._last_char:
            cmd |= CMD_CHAR
        
        # Add RLE flag if run_length > 1
        if run_length > 1:
            cmd |= CMD_RLE
        
        # Write command byte
        self._buffer.append(cmd)
        
        # Write coordinates if needed
        if needs_coords:
            self._buffer.extend(struct.pack('hh', position.x, position.y))
        
        # Write foreground color if changed
        if cmd & CMD_RGB:
            self._buffer.extend([int(pixel.color.r * 255), int(pixel.color.g * 255), int(pixel.color.b * 255)])
            self._last_fg_color = pixel.color
        
        # Write background color if changed
        if cmd & CMD_BG:
            self._buffer.extend([
                int(pixel.color_background.r * 255),
                int(pixel.color_background.g * 255),
                int(pixel.color_background.b * 255)
            ])
            self._last_bg_color = pixel.color_background
        
        # Write character if changed
        if cmd & CMD_CHAR:
            char_bytes = (pixel.char[0] if pixel.char else ' ').encode('utf-8')
            self._buffer.append(len(char_bytes))
            self._buffer.extend(char_bytes)
            self._last_char = pixel.char
        
        # Write run length if > 1
        if run_length > 1:
            self._buffer.extend(struct.pack('H', run_length))
        
        # Update last position (accounting for the entire run)
        self._last_position = Position(position.x + run_length - 1, position.y)
    
    def save(self, filename: str):
        """Save the encoded video to a file."""
        compressor = zstd.ZstdCompressor(level=3)
        compressed_data = compressor.compress(self._buffer)

        self._finalize_header()
        with open(filename, 'wb') as f:
            f.write(compressed_data)

    def get_buffer(self) -> bytes:
        """Get the encoded video as bytes."""
        self._finalize_header()
        return bytes(self._buffer)