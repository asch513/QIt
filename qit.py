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

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

class QIt():
   def __init__(self,datastore_path):
      #if not config:
      #    self.config = CaseConfigParser()
      #    self.config.read('qit.ini')
      #    self.datastore = self.config['qit']['datastore']
      with open(datastore_path) as json_file:
         self.datastore = json.load(json_file)
      
   def run(self):
      self.run_urlquery()
      # add run_vt() here 

   def diff_known_search(self,r):
      new_items = set()
      for known_item in self.datastore['known']:
         for result_item in r:
            print(known_item['item'])
            print(result_item['task']['url'])
            if known_item['item'] not in result_item['task']['url']:
               new_items.add(result_item['task']['url'])
      return new_items
         
   def run_urlquery(self):
      for items in self.datastore['search']:
         search = items['item']
         print(search)
         param = ( 'q', search)
         response = requests.get('https://urlscan.io/api/v1/search/?q={}'.format(search))
         r = json.loads(response.content.decode("utf-8"))
         #for item in r["results"]:
         #   print(search,",",item['task']['url'])
            
         new_urls = self.diff_known_search(r['results'])
         if new_urls is not None:
            for url in new_urls:
               print(new_urls)
        
      

if __name__ == "__main__":
   # remove proxy if it's set
   #if 'http_proxy' in os.environ:
   #   del os.environ['http_proxy']
   #if 'https_proxy' in os.environ:
   #   del os.environ['https_proxy']

   parser = argparse.ArgumentParser(description="query internet services")
   parser.add_argument('-q', '--query', required=False, dest='hash',
      help="hash to lookup")
   parser.add_argument('-d', '--datastore', required=False, dest='datastore', default='qit.json',
      help='json storing both known items and items to query')
   parser.add_argument('--print_json_template', required=False, dest='printtemplate', action='store_true',
      help='json storing both known items and items to query')
   parser.add_argument('-f', '--file', required=False, dest='inputfile',
      help="input file of query values, 1 per line, add quotes if literals needed") 
   args = parser.parse_args()

   if args.printtemplate:
      jformat = {
           "known" :
           [
             { "item" : "http://xxx.zip" },
             { "item" : "https://blog.xxx.net/x.zip"}
           ],
           "search" :
           [
             { "item" : "firstsearchhash" },
             { "item" : "secondsearch" }
           ]
         }
      pp = pprint.PrettyPrinter(indent=4)
      pp.pprint(jformat)
      sys.exit()

   if args.hash:
      params = (
         ( 'q', args.hash),
      )
      response = requests.get('https://urlscan.io/api/v1/search/',params)
      r = json.loads(response.content.decode("utf-8"))
      for item in r["results"]:
         print(args.hash,",",item['task']['url'])

   if args.datastore:
      qit = QIt(args.datastore)
      qit.run()

