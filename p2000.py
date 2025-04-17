#!/usr/bin/env python
"""
Author : Joost Mul <joost.mul@scouting.nl>
Version: v1.0

Features:
Start a rtl_fm and multilog-ng process to listen to P2000 messages which can be captured with a DVB-T stick. These
messages are automatically converted and shown colour coded. Per message, it will show to following:
    * The message
    * Date
    * Safety region
    * City (When available)
    * Street (When available)
    * Capcode information
        * Capcode
        * Division / Location
        * Description

Need help? Send me a mail!
"""

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
parser.add_argument('-s', '--services', help='Only show a specific service. Values need to be comma separated and based on ServiceType', required=False)
parser.add_argument('-m', '--message', help='Test the procedure with a test message', required=False)

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
            return ServiceType.AMBULANCE.value
        elif (message.message.lower().startswith(('p', 'prio'))):
            return ServiceType.FIREFIGHTER.value
        elif any(s in message.message.lower() for s in ['politie', 'icnum']):
            return ServiceType.POLICE.value
        elif 'ambu' in message.message.lower():
            return ServiceType.AMBULANCE.value

        return ServiceType.UNKNOWN.value

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

    def __getEstimatedCity(self, message: Message, estimatedRegion: Region, type: ServiceType) -> City:
        # The use of the 6-letter unique acronym for a city is a dead giveaway it's that specific city, so let's check
        # that one first before we do fuzzy matching
        for city in self.__cityCache.getAllCities():
            if ' ' + city.acronym in message.message:
                return city

        # Firefight and police calls usually end with the city name and a series of 6 numbers (potentially multiple)
        if (type in [ServiceType.FIREFIGHTER.value, ServiceType.POLICE.value]):
            for city in self.__cityCache.getAllCities():
                regexes = [
                    r'%s(?:(?: [0-9]+)+)?$' % city.acronym,
                    r'%s(?:(?: [0-9]+)+)?$' % city.name,
                ]

                for regex in regexes:
                    match = re.search(regex, message.message.strip(), re.IGNORECASE)

                    if match is not None:
                        return city

        for city in self.__cityCache.getAllCities():
            if ' ' + city.name.lower() in message.message.lower():
                return city

        return City(-1, _('Unknown city'), _('Unknown city'))

    def __getEstimatedStreet(self, message: Message, region: Region, city: City, type: ServiceType) -> str:
        regexes = []
        if type == ServiceType.FIREFIGHTER.value:
            types = [
                'Liftopsluiting',
                'Stank\/hind\. lucht(?: \([^)]+\))?(?: \([^)]+\))?',
                'Contact mkb Verontr\. opp\.water(?: \([^)]+\))?',
                '(?:\([^)]+\) )?BR [a-z]+(?: \([^)]+\))?(?: \([^)]+\))?',
                '(?: \([^)]+\))?Ass\. Ambu(?: \([^)]+\))?',
                '(?: \([^)]+\))?Ass\. Politie(?: \([^)]+\))?',
                'Dier in problemen',
                'Brandgerucht',
                '(?:BR|Ongeval) wegvervoer(?: \([^)]+\))?(?: \([^)]+\))?',
                '\([^)]+\) Ongeval wegvervoer',
                'OMS (?:br|h)andmeld(?:er|ing)',
                'Nacontrole(?: \([^)]+\))?',
                'CO-melder(?: \([^)]+\))?',
                'Dienstverlening(?: \([^)]+\))?',
                'Ongeval op water(?: \([^)]+\))?(?: \([^)]+\))?',
                'Voertuig te water(?: \([^)]+\))?',
                'Wateroverlast(?: \([^)]+\))?',
                'Dier te water(?: \([^)]+\))?',
                'Buitensluiting(?: \([^)]+\))?',
                'Reanimatie(?: \([^)]+\))?',
                'Rookmelder',
                'Ongeval',
            ]

            regexes.append(r'P [0-9] (?:(?:B[A-Z]{2}-[0-9]{2,3}|\(Oefening\) [A-Z0-9-]+) )?(?:' + '|'.join(types) + ') (.*) ' + city.name)
            regexes.append(r'P [0-9] (?:(?:B[A-Z]{2}-[0-9]{2,3}|\(Oefening\) [A-Z0-9-]+) )?(?:' + '|'.join(types) + ') (.*) ' + city.acronym)
            regexes.append(r'\(Intrekken Alarm Brw\) (?:' + '|'.join(types) + ') (.*) ' + city.name)
            regexes.append(r'P\s+[0-9]\s+(?:\([^)]+\))\s+Oefening\s+(.*)\s+' + city.name)
        elif type == ServiceType.POLICE.value:
            types = [
                'Steekpartij',
                'Ongeval wegvervoer (?:letsel|materieel)',
                'Ongeval wegvervoer',
                '(?:Ongeval|Verkeer|Veiligheid en openbare orde)\/[a-z\/\.]+\/[a-z\/\. ]+ prio [0-9]',
                '(?:Aanrijding|ongeval) letsel',
                'Achtervolging',
                'Schietpartij',
                'Explosie',
                'Letsel',
            ]

            regexes.append(r'^(?:P [0-9]\s+)?(?:[0-9]+\s+)?(?:' + '|'.join(types) + ') (.*) ' + city.name)
            regexes.append(r'^Prio [0-9] (.*) ' + city.acronym + ' (?:' + '|'.join(types) + ')')
        elif type in [ServiceType.AMBULANCE.value, ServiceType.HELICOPTER.value]:
            # These regions do not show street names
            if region.id in [1,3,4,5,6,7,8,9,14,19,20,21,22,25]:
                regexes = []

            if region.id in [-1,10,11,12]:
                regexes.append(r'^(?:A|B)[0-9]+(?:\s+\(dia: [a-z]+\))?\s+[0-9]+\s+Rit\s+[0-9]+\s+(.*)\s+' + city.name)

            if region.id in [-1,13]:
                regexes.append(r'^(?:A|B)[0-9]+\s+[0-9]+\s+(.*)\s+[0-9]+\s+' + city.name)
            if region.id in [-1,15, 17]:
                regexes.append(r'^(?:A|B)[0-9]+\s+[A-Z0-9]+\s+[0-9]+\s+(.*)\s+[0-9]{4}[A-Z]{2}\s+' + city.acronym)

            if region.id in [-1,15,16,23,24]:
                regexes.append(r'^(?:A|B)[0-9]+\s+(.*)\s+' + city.acronym)
                regexes.append(r'^(?:A|B)[0-9]+\s+(.*)\s+' + city.name)

            if region.id in [-1,17,18]:
                regexes.append(r'^(?:A|B)[0-9]+(?:\s+\(dia: [a-z]+\))?\s+AMBU\s+[0-9]+(.*)\s+[0-9]{4}[A-Z]{2}\s+' + city.name)
                regexes.append(r'^(?:A|B)[0-9]+(?:\s+\(dia: [a-z]+\))?\s+AMBU\s+[0-9]+(.*)\s+[0-9]{4}[A-Z]{2}\s+' + city.acronym)

        for regex in regexes:
            match = re.search(regex, message.message.strip(), re.IGNORECASE)

            if match is not None:
                return match.group(1).strip('- ')

        return ''

    def __getEstimatedPostalCode(self, message: Message):
        match = re.search(r'([0-9]{4}[A-Z]{2})', message.message.strip(), re.IGNORECASE)

        if (match is not None):
            return match.group(1)

        return ''

    def __printMessage(self, message: Message, capcodes: Dict[str, Capcode]):
        type = self.__getEstimatedType(message, capcodes)

        specialCode = ''
        if (message.isImportant() == True):
            specialCode = ';5'

        time = message.date.strftime('%Y-%m-%d %H:%M:%S')
        estimatedRegion = self.__getEstimatedRegion(capcodes)
        if self.__config.has_option('FILTER', 'Regions'):
            if str(estimatedRegion.id) not in self.__config.get('FILTER', 'Regions').split(','):
                return

        if self.__config.has_option('FILTER', 'Services'):
            if type not in self.__config.get('FILTER', 'Services').split(','):
                return

        estimatedCity = self.__getEstimatedCity(message, estimatedRegion, type)
        if self.__config.has_option('FILTER', 'Cities'):
            if estimatedCity not in self.__config.get('FILTER', 'Cities').split(','):
                return

        estimatedStreet = self.__getEstimatedStreet(message, estimatedRegion, estimatedCity, type)
        if estimatedStreet:
            estimatedStreet = ' - ' + estimatedStreet

        estimatedPostalCode = self.__getEstimatedPostalCode(message)
        if estimatedPostalCode:
            estimatedPostalCode = ' - ' + estimatedPostalCode

        print(f"\033[{ServiceType.typeToConsoleColor(type)}{specialCode}m{_('What')} {message.message}")
        print(f"{_('When')} {time}")
        print(f"{_('Where')} {estimatedRegion.id} {estimatedRegion.name} - {estimatedCity.name}{estimatedStreet}{estimatedPostalCode}")
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
        config.set('FILTER', 'Regions', args.regions)

    if (args.services is not None):
        config.set('FILTER', 'Services', args.services)


    P2000Listener = P2000Listener(config);
    if args.message is not None:
        message = Message('FLEX|2025-04-16 18:55:05|1600/2/K/A|13.108|'+ args.message)
        P2000Listener._onMessageReceive(message)
    else:
        P2000Listener.startListening()