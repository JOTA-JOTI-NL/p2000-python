# P2000 listener
Requirements:
* MySQL Database
* Python
* mysql-connector-python

## How does it work?
This script listens to P2000 (Dutch Emergency Services Notifications) messages on 169.65 Mhz with the
help of a DVB-T Dongle and displays the message on your terminal.

A displayed message always follows the following format:
```
Wat:  MESSAGE
Tijd: TIMESTAMP
Wie
  CAPCODE (REGION/DIVISION) RECEIVER
  CAPCODE (REGION/DIVISION) ANOTHER RECEIVER
```

## How to set up
```
apt-get install rtl-sdr multimon-ng mariadb-server python
pip install mysql-connector-python
```
Then create a user in your database with a username and password and restore the `database.sql` file 
into that database.

Don't forget to add the following to `/etc/modprobe.d/blacklist-rtl.conf`:
```
blacklist dvb_usb_rtl28xxu 
blacklist rtl2832 
blacklist rtl2830  
```

Update p2000.py to make use of your created user and start p2000.py to show the messages in a nice
format!