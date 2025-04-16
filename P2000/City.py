from typing import Dict

class City:
    def __init__(self, id: int, acronym: str, name: str):
        self.id = id
        self.acronym = acronym
        self.name = name

class CityCollection:
    def __init__(self, cities: Dict[str, City]):
        self.__cities = cities

    def getAllCities(self):
        return self.__cities.values()

    @staticmethod
    def initList(dbCursor):
        dbCursor.execute("SELECT `PK_CITY`, `ACRONYM`, `NAME` FROM D_CITY")
        cities = {}
        for city in dbCursor.fetchall():
            cities[city['PK_CITY']] = (City(city['PK_CITY'], city['ACRONYM'], city['NAME']))

        return CityCollection(dict(sorted(cities.items(), key=lambda item: len(item[1].name), reverse=True)))