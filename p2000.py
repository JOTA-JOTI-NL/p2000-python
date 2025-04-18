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

from P2000.Message import Message
from P2000.Capcode import Capcode, CapcodeCollection
from P2000.ServiceType import ServiceType
from P2000.ListenerProcess import ListenerProcess
from P2000.City import City, CityCollection
from P2000.Region import Region, RegionCollection

if '_' not in locals():
    _ = gettext.gettext

parser = argparse.ArgumentParser('P2000 Listener')
parser.add_argument('-l', '--language', help='Select language to use', required=False, default='nl')
parser.add_argument('-r', '--regions', help='Only show a specific region. Values range between 1 and 26, comma separated', required=False)
parser.add_argument('-s', '--services', help='Only show a specific service. Values need to be comma separated and based on ServiceType', required=False)
parser.add_argument('-m', '--message', help='Test the procedure with a test message', required=False)
parser.add_argument('-a', '--replay-all', help='Replay all messages in the database', required=False, action='store_true')

args = parser.parse_args()
i18n = gettext.translation('base', localedir='locales', fallback=True, languages=[args.language])
i18n.install()

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

    def replayAllMessage(self):
        self.__dbCursor.execute('SELECT `PK_MESSAGE`, `RAW_MESSAGE` FROM `F_MESSAGE` ORDER BY `DATE` ASC')
        messages = self.__dbCursor.fetchall()

        for message in messages:
            self._onMessageReceive(Message(message['RAW_MESSAGE']))

    def _onMessageReceive(self, message: Message):
        for capcode in message.capcodes:
            capcodeObj = self.__capcodeCache.getCapcodeByCapcode(capcode)
            if capcodeObj is None:
                capcodeObj = Capcode(-1, capcode, _('Unknown'), ServiceType.UNKNOWN.value, '', -1)
                self.__dbCursor.execute(
                    'INSERT INTO `D_CAPCODE` (`CAPCODE`, `FK_REGION`, `DESCRIPTION`, `TYPE`, `CITY`) VALUES (%s, %s, %s, %s, %s)',
                    [
                        capcodeObj.capcode,
                        -1,
                        capcodeObj.description,
                        capcodeObj.type,
                        capcodeObj.city
                    ])
                capcodeObj.id = self.__dbCursor.lastrowid
                self.__capcodeCache.add(capcodeObj)

        self.__printMessage(message)

    def __getEstimatedType(self, message):
        typeMapping = {}
        for capcode in message.capcodes:
            capcode = self.__capcodeCache.getCapcodeByCapcode(capcode)
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

    def __getEstimatedRegion(self, message: Message) -> Region:
        capcodeRegionMap = {}
        for capcode in message.capcodes:
            capcode = self.__capcodeCache.getCapcodeByCapcode(capcode)
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
        acronymList = '|'.join(city.acronym for city in self.__cityCache.getAllCities())
        nameList = '|'.join(city.name for city in self.__cityCache.getAllCities())

        match = re.search(r'(%s)' % acronymList, message.message)
        if match is not None:
            return self.__cityCache.getCityByAcronym(match.group(1))

        # Firefight and police calls usually end with the city name and a series of 6 numbers (potentially multiple)
        if (type in [ServiceType.FIREFIGHTER.value, ServiceType.POLICE.value]):
            match = re.search(r'(%s)(?:(?: [0-9]+)+)?$' % nameList, message.message.strip(), re.IGNORECASE)

            if match is not None:
                return self.__cityCache.getCityByName(match.group(1))

        match = re.search(r'(%s)' % nameList, message.message)
        if match is not None:
            return self.__cityCache.getCityByName(match.group(1))

        return City(-1, _('Unknown city'), _('Unknown city'))

    def __getEstimatedStreet(self, message: Message, region: Region, city: City, type: ServiceType) -> str:
        regexes = []

        if type in [ServiceType.FIREFIGHTER.value, ServiceType.KNRM.value]:
            types = [
                'Liftopsluiting',
                'Stank\/hind\. lucht(?: \([^)]+\))?(?: \([^)]+\))?',
                'Contact mkb Verontr\. opp\.water(?: \([^)]+\))?',
                '(?:\([^)]+\) )?BR [a-z\/]+(?: \([^)]+\))?(?: \([^)]+\))?',
                '(?: \([^)]+\))?Ass\. Ambu(?: \([^)]+\))?',
                '(?: \([^)]+\))?Ass\. Politie(?: \([^)]+\))?',
                'Ongeval gev(?:\.|aarlijke) stof(?:fen)?(?: \([^)]+\))?(?: \([^)]+\))?',
                'Dier in problemen',
                'Brandgerucht',
                '\([^)]+\) Contact [A-Z]+',
                '(?:BR|Ongeval) wegvervoer(?: \([^)]+\))?(?: \([^)]+\))?',
                '\([^)]+\) Ongeval wegvervoer',
                'OMS (?:(?:br|h)andmeld(?:er|ing)|beheersysteem)',
                'Nacontrole(?: \([^)]+\))?',
                'CO-melder(?: \([^)]+\))?',
                'Dienstverlening(?: \([^)]+\))?',
                'Ongeval op water(?: \([^)]+\))?(?: \([^)]+\))?',
                'Voertuig te water(?: \([^)]+\))?',
                'Wateroverlast(?: \([^)]+\))?',
                'Dier te water(?: \([^)]+\))?',
                'Dier op hoogte(?: [A-Z]+)?(?: [A-Z]+)?(?: \([^)]+\))?',
                'Buitensluiting(?: \([^)]+\))?',
                'Reanimatie(?: \([^)]+\))?',
                'Contact MKB MKB [A-Z]+',
                'Rookmelder',
                'Ongeval',
            ]

            typesList = '|'.join(types)
            regexes.append(r'P [0-9] (?:(?:B[A-Z]{2}-[0-9]{2,3}|\(Oefening\) [A-Z0-9-]+) )?(?:%s) (.+) %s' % (typesList, city.name))
            regexes.append(r'P [0-9] (?:(?:B[A-Z]{2}-[0-9]{2,3}|\(Oefening\) [A-Z0-9-]+) )?(?:%s) (.+) %s' % (typesList, city.name))
            regexes.append(r'\(Intrekken Alarm Brw\) (?:%s) (.+) %s' % (typesList, city.name))
            regexes.append(r'P\s+[0-9]\s+(?:\([^)]+\))\s+Oefening\s+(.+)\s+%s' % city.name)
            regexes.append(r'P(?:rio)? [0-9]+ (.*) %s' % city.acronym)

        elif type == ServiceType.POLICE.value:
            types = [
                'Steekpartij',
                '(?:Ongeval|Verkeer|Veiligheid en openbare orde)\/[a-z\/\.]+\/[a-z\/\. ]+ prio [0-9]',
                '(?:Aanrijding|ongeval)(?:\s+wegvervoer)?(?:\s+(?:letsel|materieel))?',
                'Achtervolging',
                'Schietpartij',
                'Explosie',
                'Letsel',
            ]

            typesList = '|'.join(types)
            regexes.append(r'^(?:P [0-9]\s+)?(?:[0-9]+\s+)?(?:%s) (.+) %s' % (typesList, city.name))
            regexes.append(r'^Prio [0-9] (.+) %s (?:%s)' % (city.acronym, typesList))
            regexes.append(r'(?:%s) (.*) %s' % (typesList, city.name))
        elif type in [ServiceType.AMBULANCE.value]:
            # These regions do not show street names
            if region.id in [1,3,4,5,6,7,8,9,14,19,20,21,22,25]:
                regexes = []

            if region.id in [-1,10,11,12]:
                regexes.append(r'^(?:A|B)[0-9]+(?:\s+\(dia: [a-z]+\))?\s+[0-9]+\s+Rit\s+[0-9]+\s+(.+)\s+%s' % city.name)

            if region.id in [-1,13,17]:
                regexes.append(r'^[A-B][0-9](?: \(dia(?:\: ja)?\))?(?: Ambu|)? [0-9]+(?: reanimatie)?(.+)\s+(?:[0-9]+)?%s' % city.acronym)
                regexes.append(r'^[A-B][0-9](?: \(dia(?:\: ja)?\))?(?: Ambu|)? [0-9]+(?: reanimatie)?(.+)\s+(?:[0-9]+)?%s' % city.name)
                regexes.append(r'^(?:A|B)[0-9]+\s+[0-9]+\s+(.+)\s+[0-9]+\s+%s' % city.name)

            if region.id in [-1,15, 17]:
                regexes.append(r'^(?:A|B)[0-9]+\s+[A-Z0-9]+\s+[0-9]+\s+(.+)\s+[0-9]{4}[A-Z]{2}\s+%s' % city.acronym)

            if region.id in [-1,15,16,23,24]:
                regexes.append(r'^(?:A|B)[0-9]+\s+(.+)\s+%s' % city.acronym)
                regexes.append(r'^(?:A|B)[0-9]+\s+(.+)\s+%s' % city.name)

            if region.id in [-1,17,18]:
                regexes.append(r'^(?:A|B)[0-9]+(?:\s+\(dia: [a-z]+\))?\s+AMBU\s+[0-9]+(.+)\s+[0-9]{4}[A-Z]{2}\s+%s' % city.name)
                regexes.append(r'^(?:A|B)[0-9]+(?:\s+\(dia: [a-z]+\))?\s+AMBU\s+[0-9]+(.+)\s+[0-9]{4}[A-Z]{2}\s+%s' % city.acronym)
        elif type == ServiceType.HELICOPTER.value:
            regexes.append(r'^[A-B][0-9](?: \(dia(?:\: ja)?\))?(?: Ambu|)? [0-9]+(?: reanimatie)?(.+)\s+(?:[0-9]+)?%s' % city.acronym)
            regexes.append(r'^[A-B][0-9](?: \(dia(?:\: ja)?\))?(?: Ambu|)? [0-9]+(?: reanimatie)?(.+)\s+(?:[0-9]+)?%s' % city.name)
        elif type == ServiceType.CITY.value:
            for capcode in message.capcodes:
                capcode = self.__capcodeCache.getCapcodeByCapcode(capcode)
                match = re.search(r'^Brugwacht(?:er)?\s+(.*)', capcode.description, re.IGNORECASE)
                if match is not None:
                    return match.group(1)

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

    def __printMessage(self, message: Message):
        type = self.__getEstimatedType(message)

        specialCode = ''
        if (message.isImportant() == True):
            specialCode = ';5'

        time = message.date.strftime('%Y-%m-%d %H:%M:%S')
        estimatedRegion = self.__getEstimatedRegion(message)
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
        estimatedPostalCode = self.__getEstimatedPostalCode(message)

        self.__storeMessage(message, estimatedRegion, estimatedCity, estimatedStreet, estimatedPostalCode, type)

        if estimatedPostalCode:
            estimatedPostalCode = ' - ' + estimatedPostalCode

        if estimatedStreet:
            estimatedStreet = ' - ' + estimatedStreet

        print(f"\033[{ServiceType.typeToConsoleColor(type)}{specialCode}m{_('What')} {message.message}")
        print(f"{_('When')} {time}")
        print(f"{_('Where')} {estimatedRegion.id} {estimatedRegion.name} - {estimatedCity.name}{estimatedStreet}{estimatedPostalCode}")
        print(f"{_('Who')}")
        for capcode in message.capcodes:
            capcode = self.__capcodeCache.getCapcodeByCapcode(capcode)
            print (f"  \033[{ServiceType.typeToConsoleColor(capcode.type)}{specialCode}m{capcode.capcode} ({capcode.city}) {capcode.description}")
        print('\033[0m')

    def __storeMessage(self, message: Message, estimatedRegion: Region, estimatedCity: City, estimatedStreet, estimatedPostalCode, type: ServiceType):
        self.__dbCursor.execute('SELECT `PK_MESSAGE`, `MESSAGE`, `STREET`, `POSTALCODE`, `FK_REGION` FROM `F_MESSAGE` WHERE `MESSAGE` = %s AND `DATE` = %s LIMIT 1', (
            message.message.strip(),
            message.date.strftime('%Y-%m-%d %H:%M:%S').strip()
        ))

        existingMessage = self.__dbCursor.fetchone()

        if existingMessage is None:
            self.__dbCursor.execute('INSERT IGNORE INTO `F_MESSAGE` (`RAW_MESSAGE`, `FK_REGION`, `FK_CITY`, `MESSAGE`, `DATE`, `STREET`, `POSTALCODE`, `TYPE`) ' +
                                    'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)', [
                message.rawMessage,
                0 if estimatedRegion is None else estimatedRegion.id,
                0 if estimatedCity is None else estimatedCity.id,
                message.message.strip(),
                message.date.strftime('%Y-%m-%d %H:%M:%S').strip(),
                '' if estimatedStreet is None else estimatedStreet,
                '' if estimatedPostalCode is None else estimatedPostalCode,
                type
            ])

            existingMessagePK = self.__dbCursor.lastrowid

            for capcode in message.capcodes:
                capcode = self.__capcodeCache.getCapcodeByCapcode(capcode)
                self.__dbCursor.execute(
                    'INSERT IGNORE INTO `X_MESSAGE_CAPCODE` (`FK_MESSAGE`, `FK_CAPCODE`) VALUES (%s, %s)', [
                        existingMessagePK,
                        capcode.id,
                    ])
                self.__db.commit()
        else:
            existingMessagePK = existingMessage['PK_MESSAGE']
            if (estimatedStreet != '' and existingMessage['STREET'] != estimatedStreet):
                self.__dbCursor.execute('UPDATE `F_MESSAGE` SET `STREET` = %s WHERE `PK_MESSAGE` = %s', [estimatedStreet,existingMessagePK])
                self.__db.commit()

            if (estimatedPostalCode != '' and existingMessage['POSTALCODE'] != estimatedPostalCode):
                self.__dbCursor.execute('UPDATE `F_MESSAGE` SET `POSTALCODE` = %s WHERE `PK_MESSAGE` = %s', [estimatedPostalCode,existingMessagePK])
                self.__db.commit()

            if (estimatedRegion.id > 0 and existingMessage['FK_REGION'] != estimatedRegion):
                self.__dbCursor.execute('UPDATE `F_MESSAGE` SET `FK_REGION` = %s WHERE `PK_MESSAGE` = %s', [estimatedRegion.id, existingMessagePK])
                self.__db.commit()

if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read(os.path.dirname(os.path.realpath(__file__)) + '/config.ini')
    if (config.has_section('FILTER') == False):
        config.add_section('FILTER')

    if (args.regions is not None):
        config.set('FILTER', 'Regions', args.regions)

    if (args.services is not None):
        config.set('FILTER', 'Services', args.services)

    P2000Listener = P2000Listener(config)
    if args.message is not None:
        message = Message('FLEX|2025-04-16 18:55:05|1600/2/K/A|13.108|'+ args.message)
        P2000Listener._onMessageReceive(message)
    elif args.replay_all is True:
        P2000Listener.replayAllMessage()
    else:
        P2000Listener.startListening()