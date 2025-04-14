#!/usr/bin/env python
import sys
import subprocess
from datetime import datetime
import mysql.connector

db = mysql.connector.connect(host='localhost', user='p2000', password='', database='p2000')

rtlfm = subprocess.Popen(['rtl_fm', '-f', '169.65M', '-M', 'fm', '-s', '22050', '-p', '83', '-g', '30'], stdout=subprocess.PIPE)
multimon = subprocess.Popen(['multimon-ng', '-a', 'FLEX', '-t', 'raw', '/dev/stdin'], stdin=rtlfm.stdout, stdout=subprocess.PIPE)
cursor = db.cursor()

for line in multimon.stdout:
    lineStr = line.decode('utf-8')
    stringParts = lineStr.split('|')
    if stringParts[0] != 'FLEX':
        continue

    date = datetime.now()
    try:
        date = datetime.strptime(stringParts[1], '%Y-%m-%d %H:%M:%S')
    except ValueError:
        print('Invalid date format: ' + date)
        continue

    capcodes = stringParts[4]
    message = stringParts[6].strip()

    if (
        message.lower().startswith('test') or
        message.strip() == ''
    ):
        continue

    isAmbu = False
    isBrnd = False
    isPol = False
    isGrip = False

    capcodeList = capcodes.split(' ')
    typeMapping = {}
    capCodesMap = {}
    for capcode in capcodeList:
        capcode = capcode[-7:]
        if int(capcode) > 2000000:
            continue

        capCodesMap[capcode] = ['onbekend', 'Onbekend', '']
        cursor.execute("SELECT TYPE, DESCRIPTION, CITY FROM D_CAPCODE WHERE CAPCODE = %s", [capcode])
        for entry in cursor:
            if entry[0] not in typeMapping.keys():
                typeMapping[entry[0]] = 0

            typeMapping[entry[0]] += 1
            capCodesMap[capcode] = entry

    type = 'onbekend'
    if (len(typeMapping) > 0):
        type = max(typeMapping, key=typeMapping.get)
    elif (
               message.startswith('A') or
        message.startswith('B') or
        ' MKA' in message
    ):
        type = 'ambulance'
    elif (
        message.lower().startswith('prio') or
        message.startswith('P 1') or
        message.startswith('P 2') or
        message.startswith('P 3') or
        message.startswith('P 4') or
        message.startswith('P 5')
    ):
        type = 'brandweer'
    elif (
        'politie' in message.lower() or
        'icnum' in message.lower()
    ):
        type = 'politie'

    if (
        '000120901' in capcodeList or
        '001420059' in capcodeList or
        '000923993' in capcodeList
    ):
        type = 'heli'

    if type == '' and 'ambu' in message.lower():
        type = 'ambulance'

    special = ''
    if 'GRIP' in message:
        special = 'grip'

    startCode = '0'

    if type == 'heli':
        startCode = '35'
    elif type == 'ambulance':
        startCode = '93'
    elif type == 'brandweer':
        startCode = '31'
    elif type == 'dares':
        startCode = '36'
    elif type == 'politie':
        startCode = '94'
    elif type == 'knrm' or type == 'reddingsbrigade':
        startCode = '33'
    elif type == 'gemeente':
        startCode = '32'

    if special == 'grip':
        startCode += ';5'

    print('\033[' + startCode + 'm\nWat:  ' + message)
    print('Tijd: ' + date.strftime('%Y-%m-%d %H:%M:%S'))
    print('Wie: ')
    for capcode, entry in capCodesMap.items():
        print ('  ' + capcode + ' (' + entry[2] + ') ' + entry[1])

    print('\033[0m')

