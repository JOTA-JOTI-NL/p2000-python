# P2000 listener - :netherlands:
For :gb: see below

Benodigdheden:
* Compuiter met Linux (Debian, Ubuntu of Raspberry Pi OS heeft de voorkeur)
* MySQL Database
* Python
* mysql-connector-python

## Hoe werkt het?
Dit script luistert naar P2000 (Notificatiesysteem voor hulpdoensten) berichten op 169.65Mhz, met behulp van een DVB-T
dongle en geeft het bericht op een duidelijk manier weer op je scherm

Een gedetailleerd bericht ziet er als volgt uit:
```
Wat:     BERICHT
Wanneer: DATUM + TIJDSTIP
Waar:    VEILIGHEIDSREGIO + STAD
Wie:
  CAPCODE (REGIO/DIVISIE) BESCHRIJVING ONTVANGER
  CAPCODE (REGIO/DIVISIE) BESCHRIJVING ANDERE ONTVANGER
```

## Hoe in te stellen
* Installeer de volgende applicaties
```
apt-get install rtl-sdr multimon-ng mariadb-server python
pip install mysql-connector-python
```

* Voeg het volgende toe aan `/etc/modprobe.d/blacklist-rtl.conf`:
```
blacklist dvb_usb_rtl28xxu 
blacklist rtl2832 
blacklist rtl2830  
```
* Maak een MySQL gebruiker aan in je Database met een gebruikersnaam en wachtwoord.
* maak een bestand aan met de naam `config.ini` in dezelfde folder als waar p2000.py staat en vul hier de juiste
  (database) instellingen in.(zie `config.ini.example` als voorbeeld voor je instellingen)
* Als laatste, start `p2000.py` en je krijgt nu de berichten op je scherm te zien!

## Parameters
Op dit moment zijn de volgende parameters mogelijk om mee te geven aan het script:
* `-l` `--language`: Geef een taal op die gebruikt moet worden. Op dit moment zijn de ondersteunde talen:
  * `nl` (:netherlands:)
  * `en` (:gb:)

# P2000 listener - :gb:
Requirements:
* MySQL Database
* Python
* mysql-connector-python

## How does it work?
This script listens to P2000 (Dutch Emergency Services Notifications) messages on 169.65 Mhz with the  help of a 
DVB-T Dongle and displays the message on your terminal.

A displayed message always follows the following format:
```
What:  MESSAGE
When:  TIMESTAMP
Where: SAFETY REGION + CITY
Who:
  CAPCODE (REGION/DIVISION) RECEIVER
  CAPCODE (REGION/DIVISION) ANOTHER RECEIVER
```

## How to set up
* Install the required applications
```
apt-get install rtl-sdr multimon-ng mariadb-server python
pip install mysql-connector-python
```

* Add the following to `/etc/modprobe.d/blacklist-rtl.conf`:
```
blacklist dvb_usb_rtl28xxu 
blacklist rtl2832 
blacklist rtl2830  
```
* Create a MySQL user in your database with a username and password.
* Create a `config.ini` file in the same directory as p2000.py and set the database credentials in there
(see `config.ini.example` as a base of what fields can be set)
* Lastly, start `p2000.py` to show the messages in a nice format!

## Parameters
At this time the following parameters are supported
* `-l` `--language`: Specify which language the script should run in. Supported options are:
  * `nl` (:netherlands:)
  * `en` (:gb:)

# Data Sources
* City acronyms: https://www.c2000.nl/pagina/?itemID=3711&menuitemID[0]=187&menuitemID[1]=425&currentMenuitemID=425
* Capcodes: https://www.tomzulu10capcodes.nl/