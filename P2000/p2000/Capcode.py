from p2000 import ServiceType

class Capcode:
    def __init__(self, capcode, description, type, city, region):
        self.capcode = capcode
        self.description = description
        self.type = type
        self.city = city
        self.region = region

        if capcode in ['0120901', '1420059', '0923993']:
            self.type = ServiceType.HELICOPTER.value

        if (self.type not in ServiceType._value2member_map_):
            print('Invalid CAPCODE type: ' + self.type)