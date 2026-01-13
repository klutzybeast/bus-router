"""Bus-related utility functions."""

import logging

logger = logging.getLogger(__name__)

# Bus colors - 33 unique colors for 33+ buses
BUS_COLORS = [
    "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4",
    "#46f0f0", "#f032e6", "#bcf60c", "#fabebe", "#008080", "#e6beff",
    "#9a6324", "#000000", "#800000", "#aaffc3", "#808000", "#ffd8b1",
    "#000075", "#9370DB", "#FFB6C1", "#FF69B4", "#FF1493", "#FFD700",
    "#FFA500", "#FF4500", "#DC143C", "#8B0000", "#006400", "#228B22",
    "#20B2AA", "#00CED1", "#191970"
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
