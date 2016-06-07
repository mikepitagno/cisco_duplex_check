#!/usr/bin/env python
'''
### Cisco Catalyst Switch Duplex Status Check
usage: cisco_duplex_check.py [-h] [-d [DEVICE_NAME] | -l [DEVICE_LIST]]
                         [-c SNMP_COMMUNITY_STRING] [-p SNMP_PORT]
                         [-e EMAILFROM EMAILTO]

CLI Arguments for cisco_duplex_check.py.

optional arguments:
  -h, --help            show this help message and exit
  -d [DEVICE_NAME], --device_name [DEVICE_NAME]
                        Target Device Name
  -l [DEVICE_LIST], --device_list [DEVICE_LIST]
                        Device List
  -c SNMP_COMMUNITY_STRING, --snmp_community_string SNMP_COMMUNITY_STRING
                        Target SNMP Community String
  -p SNMP_PORT, --snmp_port SNMP_PORT
                        Target SNMP Port
  -e EMAILFROM EMAILTO, --email EMAILFROM EMAILTO
                        Email From / Email To
'''

import sys
import pprint
import smtplib
from email.mime.text import MIMEText
import argparse
from pysnmp.entity.rfc3413.oneliner import cmdgen
import yaml
import os
from os.path import expanduser

def snmp_get_v2(snmp_target, oid, display_errors=False):
  """SNMP Get function with error handling"""
  snmp_host, snmp_community_string, snmp_port = snmp_target
  snmp_host_and_port = (snmp_host, snmp_port)
  cmd_gen = cmdgen.CommandGenerator()
  (error_detected, error_status, error_index, snmp_data) = cmd_gen.getCmd(cmdgen.CommunityData(snmp_community_string), cmdgen.UdpTransportTarget(snmp_host_and_port), oid, lookupNames=True, lookupValues=True)
  if not error_detected:
    return snmp_data
  else:
    if display_errors:
      print('ERROR DETECTED: ')
      print('    %-16s %-60s' % ('error_message', error_detected))
      print('    %-16s %-60s' % ('error_status', error_status))
      print('    %-16s %-60s' % ('error_index', error_index))

def snmp_extract(snmp_data):
  """Format the SNMP response in a human-readable format"""
  if len(snmp_data) > 1:
    raise ValueError("snmp_extract only allows a single element")
  if len(snmp_data) == 0:
    return None
  else:
    return snmp_data[0][1].prettyPrint()

def snmp_check(device_name, snmp_community_string, snmp_port):
  """Run simple SNMP test on specified device to determine if SNMP is working"""
  sysdesc_oid = '1.3.6.1.2.1.1.1.0'
  snmp_target = (device_name, snmp_community_string, snmp_port)
  snmp_data = snmp_get_v2(snmp_target,sysdesc_oid)
  return snmp_data

def snmpwalk_v2(snmp_target, oid):
  """snmpwalk"""
  snmp_host, snmp_community_string, snmp_port = snmp_target
  snmp_host_and_port = (snmp_host, snmp_port)
  cmdGen = cmdgen.CommandGenerator()
  errorIndication, errorStatus, errorIndex, varBindTable = cmdGen.nextCmd(cmdgen.CommunityData(snmp_community_string), cmdgen.UdpTransportTarget(snmp_host_and_port), oid)
  if errorIndication:
      print(errorIndication)
  else:
      if errorStatus:
          print('%s at %s' % (
              errorStatus.prettyPrint(),
              errorIndex and varBindTable[-1][int(errorIndex)-1] or '?'
              )
          )
      else:
          device_list = []
          for varBindTableRow in varBindTable:
              for name, val in varBindTableRow:
                  name = name.prettyPrint().split('1.3.6.1.2.1.2.2.1.2.')[1]
                  device_list.append(name)
          return device_list

def create_full_dict(args, snmp_community_string, snmp_port):
  """Generate and return full and half duplex dictionaries for all devices specified with either -l or -d argument"""
  half_duplex_dict = {}
  full_duplex_dict = {}
  if args.device_list is not None:
    for line in args.device_list:
      device_name = line.strip('\n')
      snmp_data = snmp_check(device_name, snmp_community_string, snmp_port)
      if snmp_data is not None: 
        half_duplex_dict[device_name], full_duplex_dict[device_name] = create_device_dict(device_name, snmp_community_string, snmp_port, half_duplex_dict, full_duplex_dict)
      else:
        half_duplex_dict[device_name] = {'SNMP Failure': 'Check Device SNMP Settings'}
        full_duplex_dict[device_name] = {'SNMP Failure': 'Check Device SNMP Settings'}
  else:
    device_name = args.device_name
    half_duplex_dict[device_name], full_duplex_dict[device_name] = create_device_dict(device_name, snmp_community_string, snmp_port, half_duplex_dict, full_duplex_dict)
  return half_duplex_dict, full_duplex_dict  

def create_device_dict(device_name, snmp_community_string, snmp_port, half_duplex_dict, full_duplex_dict):
  """Generate and return individual device dictionaries to populate full and half duplex dictionaries"""
  snmp_target = (device_name, snmp_community_string, snmp_port)
  device_int_dict = create_device_int_dict(snmp_target)
  int_up_list = create_int_up_list(device_int_dict, snmp_target)
  half_duplex_list, full_duplex_list = find_duplex(int_up_list, snmp_target)
  half_duplex_dict[device_name], full_duplex_dict[device_name] = get_int_detail(half_duplex_list, full_duplex_list, device_int_dict)
  dump_to_yaml(half_duplex_dict[device_name], full_duplex_dict[device_name], device_name)
  return half_duplex_dict[device_name], full_duplex_dict[device_name]

def create_device_int_dict(snmp_target):
  """ Generate and return a list of all interfaces for specified device; Check for saved file before running SNMP"""
  device_name = snmp_target[0].upper()
  try:
    with open("%s/%s-all_int.yaml" % (device_path,device_name), "r") as f:
      device_int_dict = yaml.load(f)
  except IOError:
    pass
    ifdesc_oid = '1.3.6.1.2.1.2.2.1.2'
    device_int_list = snmpwalk_v2(snmp_target, ifdesc_oid)
    device_int_dict = {}
    for i in device_int_list:
      ifdesc_oid = '1.3.6.1.2.1.2.2.1.2.' + str(i)
      ifalias_oid = '1.3.6.1.2.1.31.1.1.1.18.' + str(i)
      ifdesc_snmp_data = snmp_get_v2(snmp_target, ifdesc_oid)
      ifalias_snmp_data = snmp_get_v2(snmp_target, ifalias_oid)
      ifdesc = snmp_extract(ifdesc_snmp_data)
      ifalias = snmp_extract(ifalias_snmp_data)
      device_int_dict[ifdesc_oid] = {}
      device_int_dict[ifdesc_oid]['ifdesc'] = ifdesc
      device_int_dict[ifdesc_oid]['ifalias'] = ifalias
    with open("%s/%s-all_int.yaml" % (device_path,device_name), "w") as f:
      yaml.dump(device_int_dict, f)
  return device_int_dict

def create_int_up_list(device_int_dict, snmp_target):
  """Identify the active interfaces on the switch and return in a list format"""
  int_up_list = [] 
  for i in device_int_dict.keys():
    oid = "1.3.6.1.2.1.2.2.1.8.%s" % (i.split('1.3.6.1.2.1.2.2.1.2.')[1])
    snmp_op_status_raw = snmp_get_v2(snmp_target, oid=oid, display_errors=True)
    snmp_op_status = snmp_extract(snmp_op_status_raw)
    if snmp_op_status == '1':
      int_up_list.append(i)  
    else: 
      continue
  return int_up_list

def find_duplex(int_up_list, snmp_target):
  """Identify Half and Full Duplex ports and return a separate list for each"""
  half_duplex_list = []
  full_duplex_list = []
  for i in int_up_list:
    oid_int_duplex = "1.3.6.1.2.1.10.7.2.1.19.%s" % (i.split('1.3.6.1.2.1.2.2.1.2.')[1])
    snmp_int_duplex_raw = snmp_get_v2(snmp_target, oid=oid_int_duplex, display_errors=True)
    snmp_int_duplex = snmp_extract(snmp_int_duplex_raw)  
    if snmp_int_duplex == '2':
      half_duplex_list.append(i)
    elif snmp_int_duplex == '3':
      full_duplex_list.append(i)
    else:
      continue
  return half_duplex_list, full_duplex_list

def get_int_detail(half_duplex_list, full_duplex_list, device_int_dict):
  """Get the interface name and description for half and full duplex interfaces and return in dictionary format"""
  half_duplex_dict = {}
  full_duplex_dict = {}
  for i in half_duplex_list:
    interface = "1.3.6.1.2.1.2.2.1.2.%s" % (i.split('1.3.6.1.2.1.2.2.1.2.')[1])
    int_desc = device_int_dict[interface]['ifdesc']
    int_alias = device_int_dict[interface]['ifalias']
    half_duplex_dict[int_desc] = int_alias
  for i in full_duplex_list:
    interface = "1.3.6.1.2.1.2.2.1.2.%s" % (i.split('1.3.6.1.2.1.2.2.1.2.')[1])
    int_desc = device_int_dict[interface]['ifdesc']
    int_alias = device_int_dict[interface]['ifalias']
    full_duplex_dict[int_desc] = int_alias
  return half_duplex_dict, full_duplex_dict

def dict_format(half_duplex_dict, full_duplex_dict):
  """Format dictionaries into a readable format using Pretty Print and return as string""" 
  body = ''
  for key in sorted(half_duplex_dict.keys()):
    if len(half_duplex_dict[key]) > 0:
      body += str("%s Half-Duplex Ports:\n" % key.upper())
      body += str(pprint.pformat(half_duplex_dict[key].items()))
      body += str('\n')
    else:
      body += str("%s - No Half Duplex Ports\n" % key.upper())
    body += str("%s Full Duplex Ports:\n" % key.upper())
    body += str(pprint.pformat(full_duplex_dict[key].items()))
    body += str('\n\n')
  return body

def dict_format_new(half_duplex_dict, full_duplex_dict):
  """Format dictionaries into a readable format using Pretty Print and return as string""" 
  body = ''
  half_dup_switches = []
  for key in sorted(half_duplex_dict.keys()):
    if half_duplex_dict[key].keys() == ['SNMP Failure']:
      body += str("%s - SNMP Failure\n\n" % key.upper())
      continue
    elif len(half_duplex_dict[key]) > 0:
      half_dup_switches.append(key)
      body += str("%s Half-Duplex Ports:\n" % key.upper())
      body += str(pprint.pformat(half_duplex_dict[key].items()))
      body += str('\n')
    else:
      body += str("%s - No Half Duplex Ports\n" % key.upper())
    body += str("%s Full Duplex Ports:\n" % key.upper())
    body += str(pprint.pformat(full_duplex_dict[key].items()))
    body += str('\n\n')
  hds_string = str(half_dup_switches)
  body_prepend = "Switches with Half-Duplex Ports: " + hds_string 
  body = body_prepend + '\n\n' + body
  return body

def print_dict(half_duplex_dict, full_duplex_dict):
  """Print report to standard output if email option is not specified"""
  body = dict_format_new(half_duplex_dict, full_duplex_dict)
  print body

def dump_to_yaml(half_duplex_dict, full_duplex_dict, device_name):
  with open("%s/%s-duplex.yaml" % (device_path,device_name), "w") as f:
    f.write("Half Duplex Ports: ")
    f.write(yaml.dump(half_duplex_dict))
  with open("%s/%s-duplex.yaml" % (device_path,device_name), "a") as f:
    f.write("Full Duplex Ports: ")
    f.write(yaml.dump(full_duplex_dict))

def email_dict(half_duplex_dict, full_duplex_dict, email_sender, email_receiver, smtp_server):
  """Email report to address specified in command line options"""
  body = dict_format_new(half_duplex_dict, full_duplex_dict)
  msg = MIMEText(body)
  msg['Subject'] = "Duplex Report"
  msg['From'] = email_sender
  msg['To'] = email_receiver
  s = smtplib.SMTP(smtp_server)
  s.sendmail(email_sender, [email_receiver], msg.as_string())
  s.quit()

# Main Program
def main():
  home = expanduser("~")
  global device_path 
  device_path = home + '/NETWORK_DEVICES'

  if os.path.exists(device_path) == False:
      os.makedirs(device_path)
 
  parser = argparse.ArgumentParser(description='CLI arguments for cisco_duplex_check.py.  Note: User must specify either single device with -d or device list file with -l')
  device = parser.add_mutually_exclusive_group()
  device.add_argument('-d','--device_name',type=str,help='Target Device Name',nargs='?')
  device.add_argument('-l','--device_list',type=argparse.FileType('r'),help='Device List',nargs='?')
  parser.add_argument('-c','--snmp_community_string',help='Target SNMP Community String',required=False,default='public')
  parser.add_argument('-p','--snmp_port',help='Target SNMP Port',required=False,default=161)
  parser.add_argument('-e','--email',metavar=("EMAILFROM", "EMAILTO"),help='Email From / Email To',required=False,nargs=2)
  parser.add_argument('-s','--smtp_server',help='SMTP Relay',required=False)
  args = parser.parse_args()

  snmp_community_string = args.snmp_community_string
  snmp_port = args.snmp_port
  smtp_server = args.smtp_server
  
  half_duplex_dict, full_duplex_dict = create_full_dict(args, snmp_community_string, snmp_port)

  if args.email is not None:
      email_sender = args.email[0]
      email_receiver = args.email[1]
      email_dict(half_duplex_dict, full_duplex_dict, email_sender, email_receiver, smtp_server)
      #dump_to_yaml(half_duplex_dict, full_duplex_dict)
  else:
      print_dict(half_duplex_dict, full_duplex_dict)
      #dump_to_yaml(half_duplex_dict, full_duplex_dict)

if __name__ == '__main__':
    main()
