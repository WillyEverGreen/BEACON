import colorsys
import logging

logger = logging.getLogger(__name__)


def hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex string (#RRGGBB or #RGB) to (r, g, b) tuple 0-255."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join([c*2 for c in hex_color])
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert (r, g, b) 0-255 to hex string."""
    return f"#{r:02x}{g:02x}{b:02x}"

def get_relative_luminance(r: int, g: int, b: int) -> float:
    """Calculate relative luminance based on WCAG 2.1 formula."""
    def adjust(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r_adj = adjust(r)
    g_adj = adjust(g)
    b_adj = adjust(b)
    
    return 0.2126 * r_adj + 0.7152 * g_adj + 0.0722 * b_adj

def get_contrast_ratio(v1: float | tuple, v2: float | tuple) -> float:
    """Calculate contrast ratio between two values (either RGB tuples or pre-calculated luminances)."""
    l1 = get_relative_luminance(*v1) if isinstance(v1, (tuple, list)) else v1
    l2 = get_relative_luminance(*v2) if isinstance(v2, (tuple, list)) else v2
    
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)

def find_accessible_color(fg_hex: str, bg_hex: str, target_ratio: float = 4.5) -> str:
    """
    Find the nearest accessible foreground color for a given background.
    Iterates through lightness levels in HSL space.
    """
    try:
        fg_rgb = hex_to_rgb(fg_hex)
        bg_rgb = hex_to_rgb(bg_hex)
        logger.debug(f"Color conversion: fg_rgb={fg_rgb}, bg_rgb={bg_rgb}")
    except Exception as e:
        logger.warning(f"Error parsing hex colors (fg={fg_hex}, bg={bg_hex}): {e}")
        return fg_hex

    bg_lum = get_relative_luminance(*bg_rgb)
    fg_lum = get_relative_luminance(*fg_rgb)
    current_ratio = get_contrast_ratio(fg_lum, bg_lum)
    logger.debug(f"Luminance values: fg={fg_lum:.3f}, bg={bg_lum:.3f}, ratio={current_ratio:.2f}")
    
    fg_h, fg_l, fg_s = colorsys.rgb_to_hls(fg_rgb[0]/255, fg_rgb[1]/255, fg_rgb[2]/255)
    logger.debug(f"HSL values: hue={fg_h:.3f}, lightness={fg_l:.3f}, saturation={fg_s:.3f}")
    
    if current_ratio >= target_ratio:
        logger.debug(f"Current color already meets target ratio {target_ratio}")
        return fg_hex

    # We need to change lightness. Should we go lighter or darker?
    # If background is dark, try going lighter.
    # If background is light, try going darker.
    
    # Try both directions and see which one hits the target faster or is more appropriate
    # Usually we want to move AWAY from the background luminance
    
    direction = 1 if bg_lum < 0.5 else -1
    logger.debug(f"Adjusting lightness in direction: {'lighter' if direction > 0 else 'darker'}")
    
    # Iterative search (100 steps)
    best_hex = fg_hex
    for i in range(1, 101):
        test_l = fg_l + (direction * (i / 100))
        if test_l < 0 or test_l > 1:
            break
            
        test_rgb_norm = colorsys.hls_to_rgb(fg_h, test_l, fg_s)
        test_rgb = tuple(int(round(c * 255)) for c in test_rgb_norm)
        test_lum = get_relative_luminance(*test_rgb)
        
        ratio = get_contrast_ratio(test_lum, bg_lum)
        if ratio >= target_ratio:
            return rgb_to_hex(*test_rgb)
            
    # If one direction failed, try the other as a fallback (though less likely to be "good")
    direction = -direction
    for i in range(1, 101):
        test_l = fg_l + (direction * (i / 100))
        if test_l < 0 or test_l > 1:
            break
            
        test_rgb_norm = colorsys.hls_to_rgb(fg_h, test_l, fg_s)
        test_rgb = tuple(int(round(c * 255)) for c in test_rgb_norm)
        test_lum = get_relative_luminance(*test_rgb)
        
        if get_contrast_ratio(test_lum, bg_lum) >= target_ratio:
            return rgb_to_hex(*test_rgb)
            
    return best_hex # Fallback to original

if __name__ == "__main__":
    # Test cases
    logger.info(f"White on White: {find_accessible_color('#FFFFFF', '#FFFFFF')}") # Should be a dark gray
    logger.info(f"Light Gray on White: {find_accessible_color('#CCCCCC', '#FFFFFF')}") # Should be darker
    logger.info(f"Dark Gray on Black: {find_accessible_color('#333333', '#000000')}") # Should be lighter
