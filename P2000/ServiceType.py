from enum import Enum

class ServiceType(Enum):
    UNKNOWN = 'onbekend'
    AMBULANCE = 'ambulance'
    FIREFIGHTER = 'brandweer'
    KNRM = 'knrm'
    CITY = 'gemeente'
    RESCUEBRIGADE = 'reddingsbrigade'
    POLICE = 'politie'
    DARES = 'dares'
    HELICOPTER = 'helikopter'

    @staticmethod
    def typeToConsoleColor(type):
        color = 0
        if type == ServiceType.HELICOPTER.value:
            color = '35'
        elif type == ServiceType.AMBULANCE.value:
            color = '93'
        elif type == ServiceType.FIREFIGHTER.value:
            color = '31'
        elif type == ServiceType.DARES.value:
            color = '36'
        elif type == ServiceType.POLICE.value:
            color = '94'
        elif type == ServiceType.KNRM.value or type == ServiceType.RESCUEBRIGADE.value:
            color = '33'
        elif type == ServiceType.CITY.value:
            color = '32'

        return color