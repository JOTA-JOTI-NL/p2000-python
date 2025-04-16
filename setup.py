#!/usr/bin/env python
import sys
import csv
import mysql.connector
import os
import configparser
from subprocess import Popen, PIPE

config = configparser.ConfigParser()
config.read(os.path.dirname(os.path.realpath(__file__)) + '/config.ini')
databaseConf = config['DATABASE']
db = mysql.connector.connect(
    host=databaseConf.get('Host', 'localhost'),
    user=databaseConf.get('Username', 'P2000'),
    password=databaseConf.get('Password', ''),
    database=databaseConf.get('Database', 'P2000'),
)

curDir = os.path.dirname(os.path.realpath(__file__))
cursor = db.cursor(dictionary=True)

####
## Setup Database
####
fd = open(curDir + '/setup/database.sql', 'r')
sqlFile = fd.read()
fd.close()
sqlCommands = sqlFile.split(';')

for command in sqlCommands:
    try:
        if command.strip() != '':
            cursor.execute(command)
    except Exception as e :
        print("Command skipped: ",command, repr(e))

####
## Setup regios
####
print ('Regio\'s instellen - start')
with open(curDir + '/setup/regios.csv') as regiosCsv:
    reader = csv.DictReader(regiosCsv, delimiter=',')
    for row in reader:
        cursor.execute("SELECT * FROM `D_REGION` WHERE `PK_REGION` = %s", [row['regioCode']])
        existingRegion = cursor.fetchone()
        if existingRegion is None:
            cursor.execute("INSERT INTO `D_REGION` (`PK_REGION`, `NAME`) VALUES (%s, %s)", [row['regioCode'], row['regioNaam']])
            print('Regio toegevoegd:', row['regioNaam'])
            db.commit()
        elif existingRegion['NAME'] != row['regioNaam']:
            cursor.execute("UPDATE `D_REGION` SET `NAME` = %s WHERE `PK_REGION` = %s", [row['regioNaam'], existingRegion['PK_REGION']])
            print('Regio geüpdatet:', row['regioNaam'])
            db.commit()

print ('Regio\'s installen - klaar')

####
## Setup cities
####
with open(curDir + '/setup/Afkortingen Gemeente- en plaatsnamen.csv') as acronymsCsv:
    reader = csv.DictReader(acronymsCsv, delimiter=',')
    for row in reader:
        cursor.execute("SELECT * FROM `D_CITY` WHERE `ACRONYM` = %s", [row['afkorting']])
        existingCity = cursor.fetchone()
        if existingCity is None:
            cursor.execute("INSERT INTO `D_CITY` (`ACRONYM`, `NAME`) VALUES (%s, %s)", [
                row['afkorting'],
                row['plaatsnaam']
            ])
            print('Stad toegevoegd:', row['plaatsnaam'], '(', row['afkorting'], ')')
            db.commit()
        elif (
            existingCity['NAME'] != row['plaatsnaam'] or
            existingCity['ACRONYM'] != row['afkorting']
        ):
            cursor.execute("UPDATE `D_CITY` SET `NAME ` = %s, `ACRONYM` = %s WHERE PK_CITY = %s", [
                row['plaatsnaam'],
                row['afkorting'],
                existingCity['PK_CITY']
            ])
            print('Stad geüpdatet:', row['plaatsnaam'], '(', row['afkorting'], ')')

####
## Setup capcodes per veiligheidsregio
####
print ('Capcodes instellen - start')
cursor.execute("SELECT PK_REGION FROM D_REGION ORDER BY PK_REGION ASC")
for region in cursor.fetchall():
    fileLoc = curDir + '/setup/capcodes/' + str("{:02d}".format(region['PK_REGION'])) + '.csv'
    with open(fileLoc) as csvFile:
        reader = csv.DictReader(csvFile, delimiter=',')
        for row in reader:
            # If a line does not have all information, we probably want to ignore it
            if (len(row) < 4):
                continue

            type = row['discipline']
            if type == 'BRW' or type == 'GMK' or type == 'OCB':
                type = 'brandweer'
            elif type == 'AMBU' or type == 'MKA' or type == 'LifeLiner':
                type = 'ambulance'
            elif type == 'BRUG':
                type = 'gemeente'
            elif type == 'POL':
                type = 'politie'
            elif type == 'RB':
                type = 'reddingsbrigade'
            elif type == 'KNRM' or type == 'KNRM-KWC' or type == 'KNBRD' or type == 'MIRG':
                type = 'knrm'
            elif type == 'GHOR' or type == 'BRUG':
                type = 'gemeente'
            else:
                type = 'onbekend'

            cursor.execute("SELECT * FROM `D_CAPCODE` WHERE `CAPCODE` = %s LIMIT 1", [row['capcode']])
            existingCapcode = cursor.fetchone()
            if existingCapcode is None:
                cursor.execute("INSERT INTO `D_CAPCODE` (`CAPCODE`, `FK_REGION`, `DESCRIPTION`, `TYPE`, `CITY`) VALUES (%s, %s, %s, %s, %s)", [
                    row['capcode'],
                    region['PK_REGION'],
                    row['beschrijving'],
                    type,
                    row['locatie/divisie']
                ])
                print('Capcode ', row['capcode'], ' inserted')

                db.commit()
            elif (
                existingCapcode['CAPCODE'] != row['capcode'] or
                existingCapcode['FK_REGION'] != region['PK_REGION'] or
                existingCapcode['DESCRIPTION'] != row['beschrijving'] or
                existingCapcode['TYPE'] != type or
                existingCapcode['CITY'] != row['locatie/divisie']
            ):
                cursor.execute("UPDATE `D_CAPCODE` SET `FK_REGION` = %s, `DESCRIPTION` = %s, `TYPE` = %s, `CITY` = %s WHERE `PK_CAPCODE` = %s", [
                    region['PK_REGION'],
                    row['beschrijving'],
                    type,
                    row['locatie/divisie'],
                    existingCapcode['PK_CAPCODE']
                ]);

                print('Capcode ', row['capcode'], ' updated')
                db.commit()

print ('Capcodes instellen - klaar')

cursor.close()