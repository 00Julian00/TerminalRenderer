import sys
import os
from functools import lru_cache

from blessed import Terminal

if os.name == 'nt':
    os.system('chcp 65001 >nul')

def hide_cursor():
    """Hides the cursor in the terminal."""
    sys.stdout.write('\x1b[?25l')
    sys.stdout.flush()

def show_cursor():
    """Shows the cursor in the terminal."""
    sys.stdout.write('\x1b[?25h')
    sys.stdout.flush()

def clear_screen(terminal: Terminal):
    """Clears the terminal screen."""
    print(terminal.home + terminal.clear + '\x1b[3J', end='', flush=True)

def reset_text_color(terminal: Terminal):
    """Resets the text color to default."""
    print(terminal.normal, end='', flush=True)

def print_at(pos: tuple[int, int], text: str):
    """
    Prints the given text at the specified (x, y) position in the terminal.

    Args:
        terminal (Terminal): The terminal object used to control cursor movement.
        pos (tuple[int, int]): A tuple (x, y) representing the position to print the text.
        text (str): The text to be printed at the specified position.
    """
    sys.stdout.write(get_move_sequence((pos[0], pos[1])) + text)
    sys.stdout.flush()

def write_all(fd, data):
    """
    Robustly write all data to a file descriptor, handling partial writes.
    """
    while data:
        # os.write returns the number of bytes actually written
        bytes_written = os.write(fd, data)
        if not bytes_written:
            # Should not happen with stdout unless closed, but prevents infinite loop
            break
        # Slice the data to remove the part that was just written
        data = data[bytes_written:]

def print_at_bytes(pos: tuple[int, int], text: bytearray):
    data = get_move_sequence_bytes(pos) + text
    try:
        write_all(1, data)
    except OSError:
        # Fallback if raw descriptor fails
        sys.stdout.buffer.write(data)
        sys.stdout.flush()

def clear_and_print_at(terminal: Terminal, pos: tuple[int, int], text: str):
    """
    Clears the terminal screen and prints the given text at the specified (x, y) position.

    Args:
        terminal (Terminal): The terminal object used to control cursor movement.
        pos (tuple[int, int]): A tuple (x, y) representing the position to print the text.
        text (str): The text to be printed at the specified position.
    """
    print_at(pos, terminal.home + terminal.clear + '\x1b[3J' + text)

@lru_cache(maxsize=4096)
def get_move_sequence(target: tuple[int, int]) -> str:
    """Returns the terminal escape sequence to move the cursor to the target position.
    
    Args:
        target: A tuple (x, y) representing the 0-indexed position.
    
    Returns:
        The terminal escape sequence with 1-indexed coordinates.
    """
    return f'\033[{target[1] + 1};{target[0] + 1}H'

@lru_cache(maxsize=4096)
def get_rgb_front_and_back_sequence(fr: int, fg: int, fb: int, br: int, bg: int, bb: int) -> str:
    """Returns the terminal escape sequence to set both text and background colors to the specified RGB values.
    
    Args:
        fr: Foreground red component (0-255).
        fg: Foreground green component (0-255).
        fb: Foreground blue component (0-255).
        br: Background red component (0-255).
        bg: Background green component (0-255).
        bb: Background blue component (0-255).

    Returns:
        The terminal escape sequence for the specified RGB text and background colors.
    """
    return f'\x1b[38;2;{fr};{fg};{fb}m\x1b[48;2;{br};{bg};{bb}m'

@lru_cache(maxsize=4096)
def get_move_sequence_bytes(target: tuple[int, int]) -> bytes:
    """Returns the terminal escape sequence as BYTES."""
    # We build the string, then encode it. 
    # Since this is cached, the encoding cost happens only once per position.
    return f'\033[{target[1] + 1};{target[0] + 1}H'.encode('ascii')

@lru_cache(maxsize=4096)
def get_rgb_front_and_back_sequence_bytes(fr: int, fg: int, fb: int, br: int, bg: int, bb: int) -> bytes:
    """Returns the terminal escape sequence as BYTES."""
    # f-strings are faster than manual byte concatenation in Python 
    # for this specific complexity level.
    return f'\x1b[38;2;{fr};{fg};{fb}m\x1b[48;2;{br};{bg};{bb}m'.encode('ascii')