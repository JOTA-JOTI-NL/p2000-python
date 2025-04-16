from typing import *

class Region:
    def __init__(self, id, name):
        self.id = id
        self.name = name

class RegionCollection:
    def __init__(self, regions: Dict[int, Region]):
        self.__regions = regions

    def getRegionById(self, id: int):
        if id in self.__regions.keys():
            return self.__regions[id]

        return None

    def getAllRegions(self):
        return self.__regions

    @staticmethod
    def initList(dbCursor):
        dbCursor.execute("SELECT `PK_REGION`, `NAME` FROM `D_REGION`")
        regions = {}
        for region in dbCursor.fetchall():
            regions[region['PK_REGION']] = Region(region['PK_REGION'], region['NAME'])

        return RegionCollection(regions)