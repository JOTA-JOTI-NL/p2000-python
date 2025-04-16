from enum import Enum

class ServiceType(Enum):
    UNKNOWN = 'unknown'
    AMBULANCE = 'ambulance'
    FIREFIGHTER = 'brandweer'
    KNRM = 'knrm'
    CITY = 'gemeente'
    RESCUEBRIGADE = 'reddingsbrigade'
    POLICE = 'politie'
    DARES = 'dares'
    HELICOPTER = 'helikopter'