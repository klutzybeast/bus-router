# Bus Configuration - Exact capacities from 2026 spreadsheet

BUS_CAPACITIES = {
    'Bus #01': 38,
    'Bus #02': 39,
    'Bus #03': 38,
    'Bus #04': 39,
    'Bus #05': 10,
    'Bus #06': 1,
    'Bus #07': 25,
    'Bus #08': 25,
    'Bus #09': 26,
    'Bus #10': 26,
    'Bus #11': 7,
    'Bus #12': 7,
    'Bus #13': 8,
    'Bus #14': 8,
    'Bus #15': 16,
    'Bus #16': 15,
    'Bus #17': 16,
    'Bus #18': 16,
    'Bus #19': 17,
    'Bus #20': 23,
    'Bus #21': 21,
    'Bus #22': 17,
    'Bus #23': 17,
    'Bus #24': 18,
    'Bus #25': 18,
    'Bus #26': 17,
    'Bus #27': 17,
    'Bus #28': 15,
    'Bus #29': 17,
    'Bus #30': 16,
    'Bus #31': 17,
    'Bus #32': 17,
    'Bus #33': 18,
    'Bus #34': 30  # Adjusted from 352 which seems like a typo
}

BUS_DRIVERS = {
    'Bus #01': 'Guardian (Jean Marius)',
    'Bus #14': 'Christopher',
    # Add more as they are assigned
}

BUS_COUNSELORS = {
    'Bus #01': 'Guardian (Jean Marius)',
    'Bus #14': 'Lehman (CS), Sweeney',
    # Add more as they are assigned
}

def get_bus_capacity(bus_number: str) -> int:
    """Get capacity for a specific bus"""
    return BUS_CAPACITIES.get(bus_number, 30)  # Default to 30 if not found

def get_bus_driver(bus_number: str) -> str:
    """Get driver name for a specific bus"""
    return BUS_DRIVERS.get(bus_number, 'TBD')

def get_bus_counselor(bus_number: str) -> str:
    """Get counselor name for a specific bus"""
    return BUS_COUNSELORS.get(bus_number, 'TBD')

def get_total_capacity() -> int:
    """Get total capacity across all buses"""
    return sum(BUS_CAPACITIES.values())