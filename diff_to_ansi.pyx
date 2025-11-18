from blessed import Terminal
from data import DiffBuffer
from terminal_api import get_move_sequence, get_rgb_sequence, get_rgb_background_sequence, get_rgb_front_and_back_sequence

def diff_buffer_to_ANSI(diff_buffer: DiffBuffer, terminal: Terminal) -> str:
    if not diff_buffer.buffer:
        return ""

    # Sort by y then x for more efficient drawing
    diff_buffer.buffer.sort(key=lambda p: (p[0].y, p[0].x))

    output_parts = []
    
    # Use a non-existent color to ensure the first color is always set
    current_color = (-1.0, -1.0, -1.0) 
    current_background_color = (-1.0, -1.0, -1.0)
    # Use a non-existent position to ensure the first move is always made
    current_position = (-1, -1)

    for position, pixel in diff_buffer.buffer:
        x, y = position.x, position.y
        final_color = pixel.color.to_tuple_rgb()
        final_background_color = pixel.color_background.to_tuple_rgb() if pixel.color_background else None

        # If we need to move the cursor
        if (x, y) != current_position:
            # Don't move if it's just the next character on the same line
            if not (y == current_position[1] and x == current_position[0] + 1) or (y == current_position[1] + 1 and x == 0):
                output_parts.append(get_move_sequence((x, y)))
        
        fg_changed = final_color != current_color
        bg_changed = final_background_color != current_background_color

        if fg_changed and bg_changed and final_background_color is not None:
            output_parts.append(get_rgb_front_and_back_sequence(
                int(final_color[0] * 255), int(final_color[1] * 255), int(final_color[2] * 255),
                int(final_background_color[0] * 255), int(final_background_color[1] * 255), int(final_background_color[2] * 255)
            ))
        elif fg_changed:
            output_parts.append(get_rgb_sequence(int(final_color[0] * 255), int(final_color[1] * 255), int(final_color[2] * 255)))
        elif bg_changed and final_background_color is not None:
            output_parts.append(get_rgb_background_sequence(int(final_background_color[0] * 255), int(final_background_color[1] * 255), int(final_background_color[2] * 255)))

        if fg_changed:
            current_color = final_color
        if bg_changed:
            current_background_color = final_background_color

        output_parts.append(pixel.char)
        current_position = (x, y)

    return "".join(output_parts)