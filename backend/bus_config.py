# Bus Configuration - Exact capacities (All buses are either 19 or 30 seats)

BUS_CAPACITIES = {
    'Bus #01': 30,
    'Bus #02': 30,
    'Bus #03': 30,
    'Bus #04': 30,
    'Bus #05': 30,  # Corrected from 10
    'Bus #06': 19,
    'Bus #07': 30,
    'Bus #08': 30,
    'Bus #09': 30,
    'Bus #10': 30,
    'Bus #11': 19,
    'Bus #12': 19,
    'Bus #13': 19,
    'Bus #14': 19,
    'Bus #15': 19,
    'Bus #16': 19,
    'Bus #17': 19,
    'Bus #18': 19,
    'Bus #19': 19,
    'Bus #20': 30,
    'Bus #21': 30,
    'Bus #22': 19,
    'Bus #23': 19,
    'Bus #24': 19,
    'Bus #25': 19,
    'Bus #26': 19,
    'Bus #27': 19,
    'Bus #28': 19,
    'Bus #29': 19,
    'Bus #30': 19,
    'Bus #31': 19,
    'Bus #32': 19,
    'Bus #33': 19,
    'Bus #34': 30
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