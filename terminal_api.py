import sys

from blessed import Terminal

def hide_cursor(terminal: Terminal):
    """Hides the cursor in the terminal."""
    print(terminal.hide_cursor(), end='', flush=True)

def show_cursor(terminal: Terminal):
    """Shows the cursor in the terminal."""
    print(terminal.show_cursor(), end='', flush=True)

def clear_screen(terminal: Terminal):
    """Clears the terminal screen."""
    print(terminal.home + terminal.clear + '\x1b[3J', end='', flush=True)

def reset_text_color(terminal: Terminal):
    """Resets the text color to default."""
    print(terminal.normal, end='', flush=True)

def print_at(terminal: Terminal, pos: tuple[int, int], text: str):
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
    # Terminal escape sequences use 1-indexed coordinates, so add 1 to both x and y
    return f'\033[{target[1] + 1};{target[0] + 1}H'
