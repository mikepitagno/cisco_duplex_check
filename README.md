# <<<--cisco_duplex_check-->>> #
Cisco Catalyst Switch - Duplex Status Reporting Tool
-a script to check an individual or group of Cisco Catalyst switches for any ports negotiating at half duplex and report and provide a detailed report.

# Installation Notes / Prerequisites
Script written in Python2

PySNMP Required
Debian/Ubuntu based install:
sudo apt-get install python-pip
sudo pip install pysnmp

# Usage Example (Print Report to Terminal))
user@host:~$ cisco_duplex_check.py -c 'COMMUNITY STRING' -l 'PATH TO DEVICE LIST' 

# Usage Example (Email Report)
user@host:~$ cisco_duplex_check.py -c 'COMMUNITY STRING' -l 'PATH TO DEVICE LIST' -e 'EMAIL_FROM' 'EMAIL_TO' -s 'SMTP_SERVER'

# Sample Output:
Switches with Half-Duplex Ports: ['US-SW-01', 'US-SW-02']

US-SW-01 Half-Duplex Ports:
[('FastEthernet0/21', 'DEV-SERV1')]
US-SW-01 Full Duplex Ports:
[('FastEthernet0/16', 'PRD-SERV1'),
 ('FastEthernet0/15', 'PRD-SERV2'),

US-SW-02 - No Half Duplex Ports
US-SW-02 Full Duplex Ports:
[('FastEthernet0/33', 'PRD-SERV3'),
 ('GigabitEthernet0/2', 'PRD-SERV4'),

US-SW-03 SNMP Failure
