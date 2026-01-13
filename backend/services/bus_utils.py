"""Bus-related utility functions."""

import logging

logger = logging.getLogger(__name__)

# Bus colors - 34 unique, visually distinct colors for 34 buses
BUS_COLORS = [
    "#E53935", "#43A047", "#1E88E5", "#8E24AA", "#FB8C00", "#00ACC1",
    "#D81B60", "#5E35B1", "#7CB342", "#F4511E", "#00897B", "#3949AB",
    "#C0CA33", "#6D4C41", "#546E7A", "#EC407A", "#AB47BC", "#26A69A",
    "#FDD835", "#29B6F6", "#EF5350", "#66BB6A", "#42A5F5", "#7E57C2",
    "#FFCA28", "#26C6DA", "#78909C", "#8D6E63", "#9CCC65", "#FF7043",
    "#5C6BC0", "#FFEE58", "#4DB6AC", "#BA68C8"
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
