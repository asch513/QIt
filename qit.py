#!/usr/bin/python3
import argparse
from configparser import ConfigParser
import os
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import sys
import json
import time
import pprint
from datetime import datetime, timedelta
from ace_api import Alert
import logging
import logging.config

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

class QIt():
   def __init__(self,search_file,known_file):
      self.config = ConfigParser()
      self.config.read('qit.ini')
      self.new_items = {}
      self.proxies = None
      if bool(self.config['proxy']['enabled']):
         self.proxies = {
            "http": self.config['proxy']['http_proxy'],
            "https" : self.config['proxy']['https_proxy']
         }
      if bool(self.config['ace']['enabled']):
         self.rule_name = self.config['ace']['rule_name']
         self.alert_type = self.config['ace']['alert_type']
         self.tool = self.config['ace']['tool']
         self.company_id = self.config['ace']['company_id']
         self.company_name = self.config['ace']['company_name']
         self.tags = self.config['ace']['tags']
         #self.alert_remotehost = self.config['ace']['remote_host']
      # only show last X days of matching items (only care about new sites/domains/urls)
      self.days = int(self.config['config']['lookback_days'])
      self.search_filename = search_file
      with open(search_file) as json_file:
         self.search_file = json.load(json_file)
      self.known_filename = known_file
      with open(known_file) as json_file:
         self.known_file = json.load(json_file)
      
   def run(self):
      self.run_urlquery()
      try:
         
         if bool(self.config['ace']['enabled']):
            self.submit_alert()
         self.update_known_file()
      except Exception as e:
          logging.error("unable to complete submitting and saving new data", str(e))

   def get_date(self,datestring):
      # assumes this format of data - "2018-09-04T15:45:11.971Z" - which is what urlquery uses
      # just getting the day is sufficient
      datestring = datestring[0:datestring.index('T')]
      return datetime.strptime(datestring,"%Y-%m-%d")

   def is_recent(self,datestring):
      dt = self.get_date(datestring)
      dt_now = datetime.now()
      if dt > (dt_now - timedelta(self.days)):
         return True
      return False

   def diff_known_search(self,search,r):
      new_items = {}
      for result_item in r:
         known = False
         for known_item in self.known_file['known']:
            if known_item:
               if (known_item['domain'] in result_item['page']['domain']):
                  known = True

         if not known:
            if self.is_recent(result_item['task']['time']):
               result_item['search'] = search
               new_items[result_item['page']['domain']] = result_item

      return new_items

   def run_urlquery(self):
      for item in self.search_file['search']:
         # urlquery says wait 3 seconds between queries to not get banned
         time.sleep(3)
         search = item['item']
         print(search)
         param = ( 'q', search)
         if bool(self.config['proxy']['enabled']):
            response = requests.get('http://urlscan.io/api/v1/search/?q={}'.format(search), proxies=self.proxies, verify=False)
         else:
            response = requests.get('http://urlscan.io/api/v1/search/?q={}'.format(search))
         r = json.loads(response.content.decode("utf-8"))
            
         self.new_items.update(self.diff_known_search(search,r['results']))

   def update_known_file(self):
      for item in self.new_items:
         tmp = {}
         tmp[item] = { 'search' : self.new_items[item]['search'],
                       'domain' : self.new_items[item]['page']['domain'],
                       'time'   : self.new_items[item]['task']['time'],
                       'url'    : self.new_items[item]['task']['url'] }
         pprint.pprint(tmp[item])
            
         self.known_file['known'].append(tmp[item])
         new_known = True

      with open(self.known_filename, 'w') as outfile:
        json.dump(self.known_file, outfile)
        
      
   def submit_alert(self):
      for item in self.new_items:
         # format is 2018-09-04T15:45:11.971Z
         datestring = self.new_items[item]['task']['time']
         mdy = datestring[0:datestring.index('T')]
         hms = datestring[datestring.index('T')+1:datestring.index('.')]
         newds = '{} {}'.format(mdy,hms)
         #dt = datetime.strptime(newds,"%Y-%M-%d %H:%M:%S")
         alert_title = '{} - {}'.format(self.new_items[item]['task']['url'],self.new_items[item]['task']['time'])   

         alert = Alert(
             tool=self.tool,
             tool_instance=self.tool,
             alert_type=self.alert_type,
             desc=alert_title,
             event_time=datestring,
             details=item,
             name=self.rule_name,
             company_name=self.company_name,
             company_id=self.company_id
         )
         for x in self.tags.split(','):
            alert.add_tag(x)
         alert.add_observable('fqdn',self.new_items[item]['page']['domain'],None)
         alert.add_observable('url',self.new_items[item]['task']['url'],None) 
         print(Alert)

         logging.info("submitting alert {}".format(alert.description))
         #print(self.alert_remotehost)
         for env_var in [ 'http_proxy', 'https_proxy', 'ftp_proxy' ]:
            if env_var in os.environ:
                del os.environ[env_var]
         alert.submit()
         logging.info("submitted alert {}".format(alert.description))
             

if __name__ == "__main__":

   parser = argparse.ArgumentParser(description="query internet services")
   parser.add_argument('-q', '--query', required=False, dest='hash',
      help="hash to lookup")
   parser.add_argument('-s', '--search_file', required=False, dest='search_file', default='qit.search.json',
      help='json containing the search terms')
   parser.add_argument('-k', '--known_file', required=False, dest='known_file', default='qit.known.json',
      help='json containing the domains already known')
   parser.add_argument('--print_json_template', required=False, dest='printtemplate', action='store_true',
      help='json template for searches')
   parser.add_argument('-f', '--file', required=False, dest='inputfile',
      help="input file of query values, 1 per line, add quotes if literals needed") 
   parser.add_argument('--logging-config', required=False, default='logging.ini', dest='logging_config',
        help="Path to logging configuration file.  Defaults to logging.ini")
   args = parser.parse_args()

   # initialize logging
   try:
      logging.config.fileConfig(args.logging_config)
   except Exception as e:
      sys.stderr.write("ERROR: unable to load logging config from {0}: {1}".format(
      args.logging_config, str(e)))
      sys.exit(1)

   if args.printtemplate:
      jsearchformat = {
           "search" :
           [
             { "item" : "firstsearchhash" },
             { "item" : "secondsearch" }
           ]
         }
      jknownformat = {
         "known" :
         [
         ]
         }
      pp = pprint.PrettyPrinter(indent=4)
      print("search file format:")
      pp.pprint(jsearchformat)
      print("known file format:")
      pp.pprint(jknownformat)
      sys.exit()

   if args.hash:
      params = (
         ( 'q', args.hash),
      )
      response = requests.get('https://urlscan.io/api/v1/search/',params)
      r = json.loads(response.content.decode("utf-8"))
      for item in r["results"]:
         print(args.hash,",",item['task']['url'])

   if args.search_file and args.known_file:
      qit = QIt(args.search_file,args.known_file)
      qit.run()
   else:
      print("A search file and known file are required - do --print_json_template for file content example")

