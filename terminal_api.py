import sys

from blessed import Terminal

def hide_cursor():
    """Hides the cursor in the terminal."""
    # Use direct ANSI escape sequence for cross-platform compatibility (Linux, macOS, Windows 10+)
    sys.stdout.write('\x1b[?25l')
    sys.stdout.flush()

def show_cursor():
    """Shows the cursor in the terminal."""
    # Use direct ANSI escape sequence for cross-platform compatibility (Linux, macOS, Windows 10+)
    sys.stdout.write('\x1b[?25h')
    sys.stdout.flush()

def clear_screen(terminal: Terminal):
    """Clears the terminal screen."""
    print(terminal.home + terminal.clear + '\x1b[3J', end='', flush=True)

def reset_text_color(terminal: Terminal):
    """Resets the text color to default."""
    print(terminal.normal, end='', flush=True)

def print_at(_: Terminal, pos: tuple[int, int], text: str):
    """
    Prints the given text at the specified (x, y) position in the terminal.

    Args:
        terminal (Terminal): The terminal object used to control cursor movement.
        pos (tuple[int, int]): A tuple (x, y) representing the position to print the text.
        text (str): The text to be printed at the specified position.
    """
    sys.stdout.write(get_move_sequence((pos[0], pos[1])) + text)
    sys.stdout.flush()

def clear_and_print_at(terminal: Terminal, pos: tuple[int, int], text: str):
    """
    Clears the terminal screen and prints the given text at the specified (x, y) position.

    Args:
        terminal (Terminal): The terminal object used to control cursor movement.
        pos (tuple[int, int]): A tuple (x, y) representing the position to print the text.
        text (str): The text to be printed at the specified position.
    """
    print_at(terminal, pos, terminal.home + terminal.clear + '\x1b[3J' + text)

def get_move_sequence(target: tuple[int, int]) -> str:
    """Returns the terminal escape sequence to move the cursor to the target position.
    
    Args:
        target: A tuple (x, y) representing the 0-indexed position.
    
    Returns:
        The terminal escape sequence with 1-indexed coordinates.
    """
    return f'\033[{target[1] + 1};{target[0] + 1}H'

def get_rgb_sequence(r: int, g: int, b: int) -> str:
    """Returns the terminal escape sequence to set the text color to the specified RGB value.
    
    Args:
        r: Red component (0-255).
        g: Green component (0-255).
        b: Blue component (0-255).
    
    Returns:
        The terminal escape sequence for the specified RGB color.
    """
    return f'\x1b[38;2;{r};{g};{b}m'

def get_rgb_background_sequence(r: int, g: int, b: int) -> str:
    """Returns the terminal escape sequence to set the background color to the specified RGB value.
    
    Args:
        r: Red component (0-255).
        g: Green component (0-255).
        b: Blue component (0-255).
    
    Returns:
        The terminal escape sequence for the specified RGB background color.
    """
    return f'\x1b[48;2;{r};{g};{b}m'

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