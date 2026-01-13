"""Bus-related utility functions."""

import logging

logger = logging.getLogger(__name__)

# Bus colors - 34 maximally distinct colors for visual clarity
BUS_COLORS = [
    "#FF0000",   # Bus 1 - Pure Red
    "#00FF00",   # Bus 2 - Pure Green
    "#0000FF",   # Bus 3 - Pure Blue
    "#B8860B",   # Bus 4 - Dark Goldenrod (darker yellow)
    "#FF00FF",   # Bus 5 - Pure Magenta
    "#008B8B",   # Bus 6 - Dark Cyan (darker)
    "#800000",   # Bus 7 - Dark Red (Maroon)
    "#008000",   # Bus 8 - Dark Green
    "#000080",   # Bus 9 - Dark Blue (Navy)
    "#808000",   # Bus 10 - Olive
    "#800080",   # Bus 11 - Purple
    "#008080",   # Bus 12 - Teal
    "#FFA500",   # Bus 13 - Orange
    "#FF1493",   # Bus 14 - Deep Pink
    "#00CED1",   # Bus 15 - Dark Turquoise
    "#FF4500",   # Bus 16 - Orange Red
    "#9400D3",   # Bus 17 - Dark Violet
    "#32CD32",   # Bus 18 - Lime Green
    "#DC143C",   # Bus 19 - Crimson
    "#4169E1",   # Bus 20 - Royal Blue
    "#FF8C00",   # Bus 21 - Dark Orange
    "#8B4513",   # Bus 22 - Saddle Brown
    "#6B8E23",   # Bus 23 - Olive Drab (darker chartreuse)
    "#2E8B57",   # Bus 24 - Sea Green (darker spring green)
    "#FF69B4",   # Bus 25 - Hot Pink
    "#4682B4",   # Bus 26 - Steel Blue
    "#D2691E",   # Bus 27 - Chocolate
    "#FFD700",   # Bus 28 - Gold
    "#8A2BE2",   # Bus 29 - Blue Violet
    "#5F9EA0",   # Bus 30 - Cadet Blue
    "#A52A2A",   # Bus 31 - Brown
    "#DEB887",   # Bus 32 - Burlywood
    "#6495ED",   # Bus 33 - Cornflower Blue
    "#FF7F50"    # Bus 34 - Coral
]


def get_bus_color(bus_number: str) -> str:
    """Get color for a bus number."""
    try:
        bus_num = int(''.join(filter(str.isdigit, bus_number)))
        return BUS_COLORS[(bus_num - 1) % len(BUS_COLORS)]
    except (ValueError, IndexError):
        return BUS_COLORS[0]


def is_valid_bus_number(bus_value: str) -> bool:
    """Check if a bus value is a valid bus assignment."""
    if not bus_value:
        return False
    bus_upper = bus_value.upper()
    if bus_upper == 'NONE' or bus_upper == '':
        return False
    if any(x in bus_upper for x in ['MAIN TENT', 'HOCKEY RINK', 'AUDITORIUM']):
        return False
    return bus_value.startswith('Bus')


def normalize_bus_value(bus_value: str) -> str:
    """Normalize a bus value - return empty string for NONE/invalid values."""
    if not bus_value:
        return ''
    if bus_value.upper() == 'NONE':
        return ''
    if not bus_value.startswith('Bus'):
        return ''
    return bus_value
