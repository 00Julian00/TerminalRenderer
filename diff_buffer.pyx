def compute_diff_buffer(self_buffer, other_buffer, term_width, term_height, 
                        color_threshold=0.05, render_outside_bounds=False):
    """
    Same logic as your Python version, Cython will make it fast
    """
    diff_buffer = []
    threshold_squared = color_threshold * color_threshold
    max_height = max(len(self_buffer), len(other_buffer))
    
    for y in range(max_height):
        if y >= term_height and not render_outside_bounds:
            continue
        
        self_row = self_buffer[y] if y < len(self_buffer) else []
        other_row = other_buffer[y] if y < len(other_buffer) else []
        max_width = max(len(self_row), len(other_row))
        
        for x in range(max_width):
            if x >= term_width and not render_outside_bounds:
                continue
            
            self_pixel = self_row[x] if x < len(self_row) else None
            other_pixel = other_row[x] if x < len(other_row) else None
            
            needs_update = False
            
            if (self_pixel is None) != (other_pixel is None):
                needs_update = True
            elif self_pixel is not None and other_pixel is not None:
                if self_pixel.char != other_pixel.char:
                    needs_update = True
                else:
                    r1, g1, b1 = self_pixel.color.to_tuple_rgb()
                    r2, g2, b2 = other_pixel.color.to_tuple_rgb()
                    distance_squared = (r1 - r2)**2 + (g1 - g2)**2 + (b1 - b2)**2
                    if distance_squared >= threshold_squared:
                        needs_update = True
            
            if needs_update:
                from data import Pixel, Color, Position
                pixel_to_draw = self_pixel if self_pixel is not None else Pixel(' ', Color(0, 0, 0), Position(x, y))
                diff_buffer.append(((x, y), pixel_to_draw))
    
    return diff_buffer
