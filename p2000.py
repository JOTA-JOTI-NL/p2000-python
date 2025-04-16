#!/usr/bin/env python
from unittest import case

import mysql.connector
import configparser
import os
import gettext
import argparse
import re
from typing import *

from P2000.Message import Message
from P2000.Capcode import Capcode, LifelinerCapcodes, CapcodeCollection
from P2000.ServiceType import ServiceType
from P2000.ListenerProcess import ListenerProcess
from P2000.City import City, CityCollection
from P2000.Region import Region, RegionCollection

parser = argparse.ArgumentParser('P2000 Listener')
parser.add_argument('-l', '--language', help='Select language to use', required=False, default='nl')
parser.add_argument('-r', '--regions', help='Only show a specific region. Values range between 1 and 26, comma separated', required=False)

args = parser.parse_args()
i18n = gettext.translation('base', localedir='locales', fallback=True, languages=[args.language])
i18n.install()
_ = i18n.gettext

class P2000Listener:
    def __init__(self, config: configparser.ConfigParser):
        self.__config = config

        databaseConf = config['DATABASE']
        self.__db = mysql.connector.connect(
            host=databaseConf.get('Host', 'localhost'),
            user=databaseConf.get('Username', 'P2000'),
            password=databaseConf.get('Password', ''),
            database=databaseConf.get('Database', 'P2000'),
        )

        self.__dbCursor = self.__db.cursor(dictionary=True)

        self.__cityCache = CityCollection.initList(self.__dbCursor)
        self.__capcodeCache = CapcodeCollection.initList(self.__dbCursor)
        self.__regionCache = RegionCollection.initList(self.__dbCursor)

        self.__process = ListenerProcess()
        self.__process.subscribe(self._onMessageReceive)

    def startListening(self):
        self.__process.startProcess()

    def _onMessageReceive(self, message: Message):
        capcodes = {}
        for capcode in message.capcodes:
            capcodeObj = self.__capcodeCache.getCapcodeByCapcode(capcode)
            if capcodeObj is None:
                capcodeObj = Capcode(-1, capcode, _('Unknown'), ServiceType.UNKNOWN.value, '', '')

            capcodes[capcode] = capcodeObj

        self.__printMessage(message, capcodes)

    def __getEstimatedType(self, message, capcodes: Dict[str,Capcode]):
        typeMapping = {}
        for capcode in capcodes.values():
            typeMapping[capcode.type] = typeMapping.get(capcode.type, 0) + 1

        # We should check the Capcodes for their types to be leading
        if (len(typeMapping) > 0):
            type = max(typeMapping, key=typeMapping.get)
            if type != ServiceType.UNKNOWN.value:
                return type

        # It could be that the Capcodes are not found, in that case we do some guesstimation based on certain keywords
        # which is not accurate, but hey, it's better than no type flagged
        if (message.message.startswith(('A', 'B')) or ' MKA' in message.message):
            return ServiceType.AMBULANCE
        elif (message.message.lower().startswith(('p', 'prio'))):
            return ServiceType.FIREFIGHTER
        elif any(s in message.message.lower() for s in ['politie', 'icnum']):
            return ServiceType.POLICE
        elif 'ambu' in message.message.lower():
            return ServiceType.AMBULANCE

        return ServiceType.UNKNOWN

    def __getEstimatedRegion(self, capcodes: Dict[str, Capcode]) -> Region:
        capcodeRegionMap = {}
        for capcode in capcodes.values():
            if capcode.regionId not in capcodeRegionMap.keys():
                capcodeRegionMap[capcode.regionId] = 0
            capcodeRegionMap[capcode.regionId] += 1

        if len(capcodeRegionMap) > 0:
            region = self.__regionCache.getRegionById(max(capcodeRegionMap, key=capcodeRegionMap.get))
            if region is not None:
                return region

        return Region(-1, _('Unknown region'))

    def __getEstimatedCity(self, message: Message) -> City:
        for city in self.__cityCache.getAllCities():
            if city.acronym in message.message:
                return city

        for city in self.__cityCache.getAllCities():
            if city.name in message.message:
                return city

        return City(-1, _('Unknown city'), _('Unknown city'))

    def __getEstimatedStreet(self, message: Message, region: Region, city: City, type: ServiceType) -> str:
        # This still needs to be implemented when i get a better understanding of the entire protocol
        return ''

    def __printMessage(self, message: Message, capcodes: Dict[str, Capcode]):
        type = self.__getEstimatedType(message, capcodes)

        specialCode = ''
        if (message.isImportant() == True):
            specialCode = ';5'

        time = message.date.strftime('%Y-%m-%d %H:%M:%S')
        estimatedRegion = self.__getEstimatedRegion(capcodes)
        if self.__config.has_option('FILTER', 'regions'):
            if estimatedRegion.id not in self.__config.get('FILTER', 'regions').split(','):
                print('filtered', estimatedRegion.id, 'from list', self.__config.get('FILTER', 'regions'))
                return

        estimatedCity = self.__getEstimatedCity(message)
        estimatedStreet = self.__getEstimatedStreet(message, estimatedRegion, estimatedCity, type)

        print(f"\033[{ServiceType.typeToConsoleColor(type)}{specialCode}m{_('What')} {message.message}")
        print(f"{_('When')} {time}")
        print(f"{_('Where')} {estimatedRegion.id} {estimatedRegion.name} - {estimatedCity.name} - {estimatedStreet}")
        print(f"{_('Who')}")
        for key,entry in capcodes.items():
            print (f"  \033[{ServiceType.typeToConsoleColor(entry.type)}{specialCode}m{entry.capcode} ({entry.city}) {entry.description}")
        print('\033[0m')

if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read(os.path.dirname(os.path.realpath(__file__)) + '/config.ini')
    if (config.has_section('FILTER') == False):
        config.add_section('FILTER')

    if (args.regions is not None):
        config.set('FILTER', 'regions', args.regions)

    P2000Listener = P2000Listener(config);
    P2000Listener.startListening()