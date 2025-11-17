from blessed import Terminal
from data import DiffBuffer
from terminal_api import get_move_sequence, get_rgb_sequence

def diff_buffer_to_ANSI(diff_buffer: DiffBuffer, terminal: Terminal) -> str:
    if not diff_buffer.buffer:
        return ""

    # Sort by y then x for more efficient drawing
    diff_buffer.buffer.sort(key=lambda p: (p[0].y, p[0].x))

    output_parts = []
    
    # Use a non-existent color to ensure the first color is always set
    current_color = (-1.0, -1.0, -1.0) 
    # Use a non-existent position to ensure the first move is always made
    current_position = (-1, -1)

    for position, pixel in diff_buffer.buffer:
        x, y = position.x, position.y
        final_color = pixel.color.to_tuple_rgb()

        # If we need to move the cursor
        if (x, y) != current_position:
            # Don't move if it's just the next character on the same line
            if not (y == current_position[1] and x == current_position[0] + 1):
                output_parts.append(get_move_sequence((x, y)))
        
        # Change color if different from the last one
        if final_color != current_color:
            output_parts.append(get_rgb_sequence(int(final_color[0] * 255), int(final_color[1] * 255), int(final_color[2] * 255)))
            current_color = final_color

        output_parts.append(pixel.char)
        current_position = (x, y)

    return "".join(output_parts)