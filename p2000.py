#!/usr/bin/env python
import sys
import subprocess
from datetime import datetime
import mysql.connector
import configparser
import os
from enum import Enum

class Message:
    def __init__(self, message):
        self.__rawMessage = message
        self.__stringParts = message.split('|')
        self.__isValid = True

        if (self.__stringParts[0] != 'FLEX'):
            self.__isValid = False
            return

        self.date = datetime.now()
        self.capcodes = self.__stringParts[4]
        self.capcodeList = self.capcodes.split(' ')
        self.message = self.__stringParts[6].strip()

        try:
            self._date = datetime.strptime(self.__stringParts[1], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            self.__isValid = False
            return

        if (
            self.message.lower().startswith('test') or
            self.message.strip() == ''
        ):
            self.__isValid = False
            return

    def isValidMessage(self):
        return self.__isValid

    def getEstimatedType(self, typeMapping={}):
        type = ServiceType.UNKNOWN
        if (len(typeMapping) > 0):
            type = max(typeMapping, key=typeMapping.get)
        elif (
            self.message.startswith('A') or
            self.message.startswith('B') or
            ' MKA' in message.message
        ):
            type = ServiceType.AMBULANCE
        elif (
            self.message.lower().startswith('prio') or
            self.message.startswith('P')
        ):
            type = ServiceType.FIREFIGHTER
        elif (
            'politie' in self.message.lower() or
            'icnum' in self.message.lower()
        ):
            type = ServiceType.POLICE

        for capcode in self.capcodeList:
            if capcode in ['0120901', '1420059', '0923993']:
                type = ServiceType.HELICOPTER

        if type == ServiceType.UNKNOWN and 'ambu' in self.message.lower():
            type = ServiceType.AMBULANCE

        return type

    def print(self, type, capcodes):
        special = ''
        if 'GRIP' in self.message:
            special = 'grip'

        startCode = self.__typeToColor(type)

        specialCode = ''
        if special == 'grip':
            specialCode = ';5'

        time = self.date.strftime('%Y-%m-%d %H:%M:%S')
        output = f"""\033[{startCode}{specialCode}mWat:  {self.message}
Tijd: {time}
Wie:"""
        print(output)
        for key,entry in capcodes.items():
            entryColor = self.__typeToColor(entry.type)
            print (f"  \033[{entryColor}{specialCode}m{entry.capcode} ({entry.city}) {entry.description}")
        print('\033[0m')

    def __typeToColor(self, type):
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

class P2000:
    def __init__(self, config):
        self.__config = config

        databaseConf = config['DATABASE']
        self.__db = mysql.connector.connect(
            host=databaseConf.get('Host', 'localhost'),
            user=databaseConf.get('Username', 'p2000'),
            password=databaseConf.get('Password', ''),
            database=databaseConf.get('Database', 'p2000'),
        )

        self.__dbCursor = self.__db.cursor()

    def startListening(self):
        rtlfm = subprocess.Popen(['rtl_fm', '-f', '169.65M', '-M', 'fm', '-s', '22050', '-p', '83', '-g', '30'], stdout=subprocess.PIPE)
        multimon = subprocess.Popen(['multimon-ng', '-a', 'FLEX', '-t', 'raw', '/dev/stdin'], stdin=rtlfm.stdout, stdout=subprocess.PIPE)

        for line in multimon.stdout:
            lineStr = line.decode('utf-8')
            message = Message(lineStr)

            if message.isValidMessage() == False:
                continue

            typeMapping = {}
            capcodes = {}
            for capcode in message.capcodes.split(' '):
                capcode = capcode[-7:]
                # Capcodes larger than 2000000 are usually monitoring groups so they can be ignores
                if int(capcode) > 2000000:
                    continue

                self.__dbCursor.execute("""
                    SELECT
                        c.CAPCODE,
                        c.DESCRIPTION,
                        c.TYPE,
                        c.CITY,
                        r.NAME
                    FROM D_CAPCODE c
                    LEFT JOIN D_REGION r ON c.FK_REGION = r.PK_REGION
                    WHERE c.CAPCODE = %s""",
                    [capcode]
                )

                found = False
                columns = [col[0] for col in self.__dbCursor.description]
                for entry in self.__dbCursor:
                    found = True
                    entry = dict(zip(columns, entry))
                    capcode = Capcode(entry['CAPCODE'], entry['DESCRIPTION'], entry['TYPE'], entry['CITY'], entry['NAME'])
                    capcodes[capcode] = capcode
                    if capcode.type not in typeMapping.keys():
                        typeMapping[capcode.type] = 0

                    typeMapping[capcode.type] += 1

                if found == False:
                    capcodes[capcode] = Capcode(capcode, 'Onbekend', ServiceType.UNKNOWN.value, '', '')

            type = message.getEstimatedType(typeMapping)
            message.print(type, capcodes)

if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read(os.path.dirname(os.path.realpath(__file__)) + '/config.ini')

    p2000 = P2000(config);
    p2000.startListening()