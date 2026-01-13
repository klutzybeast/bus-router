# Bus Configuration with Home Locations
# Each bus has ONE home location used for:
# - AM Start Point (where bus starts morning route)
# - PM End Point (where bus ends afternoon route)

# Camp address (constant)
CAMP_ADDRESS = "477 Ocean Avenue, East Rockaway, NY 11518"

# Bus Location Names (for seat availability sheet)
BUS_LOCATIONS = {
    'Bus #01': 'Valley Stream',
    'Bus #02': 'East Rockaway',
    'Bus #03': 'Rockville Centre',
    'Bus #04': 'Valley Stream',
    'Bus #05': 'East Rockaway',
    'Bus #06': 'Woodmere',
    'Bus #07': 'Oceanside',
    'Bus #08': 'Rockville Centre',
    'Bus #09': 'Oceanside',
    'Bus #10': 'Rockville Centre',
    'Bus #11': 'Rockville Centre',
    'Bus #12': 'Rockville Centre',
    'Bus #13': 'Rockville Centre',
    'Bus #14': 'Long Beach',
    'Bus #15': 'Long Beach',
    'Bus #16': 'Oceanside',
    'Bus #17': 'Baldwin',
    'Bus #18': 'Oceanside',
    'Bus #19': 'Oceanside',
    'Bus #20': 'Oceanside',
    'Bus #21': 'Rockville Centre',
    'Bus #22': 'Baldwin',
    'Bus #23': 'Rockville Centre',
    'Bus #24': 'Rockville Centre',
    'Bus #25': 'Malverne',
    'Bus #26': 'Merrick',
    'Bus #27': 'Lynbrook',
    'Bus #28': 'Oceanside',
    'Bus #29': 'Lynbrook',
    'Bus #30': 'Lynbrook',
    'Bus #31': 'Island Park / Oceanside',
    'Bus #32': 'Rockville Centre',
    'Bus #33': 'Rockville Centre',
    'Bus #34': 'Freeport'
}

# Bus Capacities (19-seater or 30-seater)
BUS_CAPACITIES = {
    'Bus #01': 30,
    'Bus #02': 30,
    'Bus #03': 30,
    'Bus #04': 30,
    'Bus #05': 30,
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

# Bus Drivers
BUS_DRIVERS = {
    'Bus #01': 'Guardian (Jean Marius)',
    'Bus #14': 'Christopher',
    'Bus #31': 'Bus 31 Driver',
    # Add more as they are assigned
}

# Bus Counselors
BUS_COUNSELORS = {
    'Bus #01': 'Guardian (Jean Marius)',
    'Bus #14': 'Lehman (CS), Sweeney',
    # Add more as they are assigned
}

# Home Locations for Each Bus
# This is where the bus:
# - STARTS in the AM (before picking up campers)
# - ENDS in the PM (after dropping off all campers)
# If home_location = CAMP_ADDRESS, bus starts/ends at camp
# If home_location = driver's address, bus starts/ends at driver's home
BUS_HOME_LOCATIONS = {
    'Bus #01': CAMP_ADDRESS,  # Starts and ends at camp
    'Bus #02': CAMP_ADDRESS,
    'Bus #03': CAMP_ADDRESS,
    'Bus #04': CAMP_ADDRESS,
    'Bus #05': CAMP_ADDRESS,
    'Bus #06': CAMP_ADDRESS,
    'Bus #07': CAMP_ADDRESS,
    'Bus #08': CAMP_ADDRESS,
    'Bus #09': CAMP_ADDRESS,
    'Bus #10': CAMP_ADDRESS,
    'Bus #11': CAMP_ADDRESS,
    'Bus #12': CAMP_ADDRESS,
    'Bus #13': CAMP_ADDRESS,
    'Bus #14': CAMP_ADDRESS,
    'Bus #15': CAMP_ADDRESS,
    'Bus #16': CAMP_ADDRESS,
    'Bus #17': CAMP_ADDRESS,
    'Bus #18': CAMP_ADDRESS,
    'Bus #19': CAMP_ADDRESS,
    'Bus #20': CAMP_ADDRESS,
    'Bus #21': CAMP_ADDRESS,
    'Bus #22': CAMP_ADDRESS,
    'Bus #23': CAMP_ADDRESS,
    'Bus #24': CAMP_ADDRESS,
    'Bus #25': CAMP_ADDRESS,
    'Bus #26': CAMP_ADDRESS,
    'Bus #27': CAMP_ADDRESS,
    'Bus #28': CAMP_ADDRESS,
    'Bus #29': CAMP_ADDRESS,
    'Bus #30': CAMP_ADDRESS,
    'Bus #31': "4288 New York Avenue, Island Park, NY 11558",  # Driver's home
    'Bus #32': CAMP_ADDRESS,
    'Bus #33': CAMP_ADDRESS,
    'Bus #34': CAMP_ADDRESS,
}


def get_bus_capacity(bus_number: str) -> int:
    """Get capacity for a specific bus"""
    return BUS_CAPACITIES.get(bus_number, 30)


def get_bus_driver(bus_number: str) -> str:
    """Get driver name for a specific bus"""
    return BUS_DRIVERS.get(bus_number, 'TBD')


def get_bus_counselor(bus_number: str) -> str:
    """Get counselor name for a specific bus"""
    return BUS_COUNSELORS.get(bus_number, 'TBD')


def get_bus_home_location(bus_number: str) -> str:
    """
    Get the home location for a specific bus.
    This is used for:
    - AM route START point
    - PM route END point
    """
    return BUS_HOME_LOCATIONS.get(bus_number, CAMP_ADDRESS)


def is_home_at_camp(bus_number: str) -> bool:
    """Check if the bus's home location is the camp"""
    return get_bus_home_location(bus_number) == CAMP_ADDRESS


def get_camp_address() -> str:
    """Get the camp address constant"""
    return CAMP_ADDRESS


def get_total_capacity() -> int:
    """Get total capacity across all buses"""
    return sum(BUS_CAPACITIES.values())


def get_all_buses() -> list:
    """Get list of all bus numbers"""
    return list(BUS_CAPACITIES.keys())


def get_bus_info(bus_number: str) -> dict:
    """Get complete info for a bus"""
    home_loc = get_bus_home_location(bus_number)
    return {
        'bus_number': bus_number,
        'capacity': get_bus_capacity(bus_number),
        'driver': get_bus_driver(bus_number),
        'counselor': get_bus_counselor(bus_number),
        'home_location': home_loc,
        'home_is_camp': home_loc == CAMP_ADDRESS,
        'home_label': 'Camp' if home_loc == CAMP_ADDRESS else 'Driver Home'
    }
