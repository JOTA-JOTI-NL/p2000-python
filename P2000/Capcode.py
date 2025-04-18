from P2000.ServiceType import ServiceType
from enum import Enum
from typing import Dict

class Capcode:
    def __init__(self, id: int, capcode: str, description: str, type: str, city: str, regionId: int):
        self.id = id
        self.capcode = capcode
        self.description = description
        self.type = type
        self.city = city
        self.regionId = regionId

        if capcode in LifelinerCapcodes._value2member_map_:
            self.type = ServiceType.HELICOPTER.value

        if (self.type not in ServiceType._value2member_map_):
            print('Invalid CAPCODE type: ' + self.type)

class LifelinerCapcodes(Enum):
    LIFELINER1 = '0120901'
    LIFELINER2 = '1420059'
    LIFELINER3 = '0923993'

class CapcodeCollection(object):
    def __init__(self, capcodes: Dict[str,Capcode]):
        self.__capcodes = capcodes

    def getCapcodeByCapcode(self, capcode: str) -> Capcode:
        if capcode in self.__capcodes.keys():
            return self.__capcodes[capcode]

        return None

    def add(self, capcode: Capcode):
        self.__capcodes[capcode.capcode] = capcode

    @staticmethod
    def initList(dbCursor):
        dbCursor.execute("SELECT `PK_CAPCODE`, `CAPCODE`, `FK_REGION`, `DESCRIPTION`, `TYPE`, `CITY` FROM D_CAPCODE")
        capcodes = {}
        for capcode in dbCursor.fetchall():
            capcodes[capcode['CAPCODE']] = Capcode(
                capcode['PK_CAPCODE'],
                capcode['CAPCODE'],
                capcode['DESCRIPTION'],
                capcode['TYPE'],
                capcode['CITY'],
                capcode['FK_REGION']
            )

        return CapcodeCollection(capcodes)