#!/usr/bin/env python3
import tarfile
import json
import os
import inspect
import re
import uuid
import math
import shlex
import shutil
import logging
import sys
import requests
import glob
import pandas as pd
import numpy as np
from tracemalloc import start
import textfsm
from pprint import pprint as pp
current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir) 
from requests.exceptions import HTTPError
from app.mapImportLogger import logger

logger = logging.getLogger('MapImporter.WingImporter')

log_ap_floor_cfg = False


PATH = current_dir
os.environ["NET_TEXTFSM"]='{}/templates/'.format(PATH)

class Wing:
    def __init__(self, filename, APNoFloorLogging=True, GEOAPILogging=True, geoApiKey = ''):
        self.filename = filename
        self.APNoFloorLogging = APNoFloorLogging
        self.GEOAPILogging = GEOAPILogging
        if geoApiKey:
            self.apiKey = geoApiKey
            self.geo_coords = True
        else:
            self.geo_coords = False
        self.projectFolder = f"{PATH}/project"
        if os.path.exists(self.projectFolder) and os.path.isdir(self.projectFolder):
            shutil.rmtree(self.projectFolder)

        self.cc_df = pd.read_csv(f"{PATH}/cc_map.csv")
        

    def __convertToDict(self, lst, domain):
        temp_list = lst.copy()
        temp_list.pop(0)
        temp_list = temp_list[::2]
        return temp_list
    
    def __validResponse(self, options, count):
        validResponse = False
        while validResponse != True:
            print("\nPlease select one of the following: ")
            for option in options:
                print(option)
            selection = input(f"Please enter 1 - {count}: ")
            try:
               selection = int(selection)  
            except:
                print("Please enter a valid response!!\n")
                continue
            if 0 < selection <= count:
                 validResponse = True
        return selection

    def __addressFromGeoCoor(self, lat_coor, long_coor):
        url = f"https://revgeocode.search.hereapi.com/v1/revgeocode?at={lat_coor},{long_coor}&apikey={self.apiKey}"
        try:
            response = requests.get(url)
        except HTTPError as http_err:
            raise ValueError(f'HTTP error occurred: {http_err}') 
        if response is None:
            log_msg = "ERROR: No response received from revgeocode API!"
            raise ValueError(log_msg)
        if response.status_code != 200:
            try:
                data = response.json()
            except json.JSONDecodeError:
                log_msg = f"Error - HTTP Status Code: {str(response.status_code)}"
                logger.warning(f"\t\t{response.text}")
            else:
                log_msg = "Reverse Geo coordinates API failed with error: " + data['error']
            raise ValueError(log_msg)  
        try:
            data = response.json()
        except json.JSONDecodeError:
            logger.error(f"Unable to parse json data - {url} - HTTP Status Code: {str(response.status_code)}")
            raise ValueError("Unable to parse the data from json, script cannot proceed")
        address = (f"{data['items'][0]['address']['houseNumber']} {data['items'][0]['address']['street']}")
        city = (data['items'][0]['address']['city'])
        state = (data['items'][0]['address']['stateCode'])
        postal_code= (data['items'][0]['address']['postalCode'])
        address_dic = {
            "address": address,
            "city": city,
            "state": state,
            "postal_code": postal_code
        }
        sys.stdout.flush()
        return address_dic

    def __getRfDomainInfo(self):
        #domain info
        domain_data = []
        for domain in self.rfDomains:
            with open(f'{PATH}/templates/wing_rfdomain.textfsm') as f:
                domain_template = textfsm.TextFSM(f)
            my_regex = r"\nrf-domain\s" + re.escape(domain) + r"\n(.*?)\n\s?!"
            domainInfo = re.findall(my_regex, self.startupContent, re.DOTALL)[0]
            data = domain_template.ParseText(domainInfo)   
            try:
                data = [dict(zip(domain_template.header, row)) for row in data][0]
                data['name'] =  domain
                if data['locationTree']:
                    items = shlex.split(data['locationTree'])
                    loc_dic = self.__convertToDict(items, domain)
                    data['locationTree'] = loc_dic
                else:
                    data['locationTree'] = ["Site-" + domain]
            except IndexError:
                data = {'name': domain, 'locationTree': ["Site-" + domain], 'floors': [], 'countryCode':'us'}
            if 'geo_coor' in data:
                if self.geo_coords:
                    lat_coor, long_coor = data['geo_coor'].split()
                    try:
                        address = self.__addressFromGeoCoor(lat_coor, long_coor)
                    except ValueError as e:
                        logger.error(e)
                        print(f"\n{e} trying to get address for rf-domain {data['name']}\nContinuing to gather data....", end='')
                        logger.error(f"Address import failed. 'Unknown Address' will be used for {data['name']}")
                        address = {
                            "address": "Unknown",
                            "city": "Unknown",
                            "state": "Unknown",
                            "postal_code": "Unknown"
                        }
                    except:
                        log_msg = (f"Unknown error occurred with reverse Geo coordinates API with rf-domain {data['name']}")
                        logger.error(log_msg)
                        print(f"{log_msg}\nContinuing to gather data....", end='')
                        logger.error(f"Address import failed. 'Unknown Address' will be used.")
                        address = {
                            "address": "Unknown",
                            "city": "Unknown",
                            "state": "Unknown",
                            "postal_code": "Unknown"
                        }
                else:
                    if self.GEOAPILogging == True:
                        logger.warning(f"No API key was found for geo coordinates. Geo coordinates cannot be changed to physical address for rf-domain {data['name']}")
                        print("\nNo API key was found for geo coordinates to do reverse geo coordinates. If you would like to get building addresses in XIQ from the geo coordinates please add an API key for platform.here.com")
                        print("More information can be found in the readme.md file.\nContinuing to gather data....", end='')
                    address = {
                        "address": "Unknown",
                        "city": "Unknown",
                        "state": "Unknown",
                        "postal_code": "Unknown"
                    }
            else:
                address = {
                    "address": "Unknown",
                    "city": "Unknown",
                    "state": "Unknown",
                    "postal_code": "Unknown"
                }

            data['address'] = address
            if data['countryCode'] == '':
                data['countryCode'] = 'us'
            # change Country ISO to County Code - uses CSV file cc_map.csv
            filt = self.cc_df['ISO'] == data['countryCode']
            cc =  "Unknown" if pd.isna(self.cc_df.loc[filt,'CODE'].values[0]) else int(self.cc_df.loc[filt,'CODE'].values[0])
            if cc == "Unknown":
                logger.error(f"{data['name']}'s country ISO was not found. Defaulting to US 840. You can change later if needed.")
                data['countryCode'] = 840
            else:
                data['countryCode'] = cc
            domain_data.append(data)
        return(domain_data)


    def exportFile(self):
        data = {} 
        try:
            flag=tarfile.is_tarfile(self.filename)
        except FileNotFoundError:
            log_msg = f"{self.filename} file does not exist"
            logger.error(log_msg)
            raise ValueError(log_msg)   
            
        if flag:
            try:
                file_obj = tarfile.open(self.filename, 'r')
                file_obj.extractall('app/project')
                file_obj.close()
            except EOFError:
                logger.warning(f'EOFError for {self.filename} when extracting. Attempting script anyways, but possibly a corrupt file was used')
                if file_obj:
                    file_obj.close()
        
        self.rfDomains = []
        try:
            with open(f"{self.projectFolder}/output/cli.show_global_domain_managers", "r") as f:
                content = f.read().splitlines()
                content = content[4:-2]
                for line in content:
                    self.rfDomains.append(re.sub(r"\s+", " ", line).split(" ")[1])
        except FileNotFoundError:
            log_msg = "cli.show_global_domain_managers was not found in output folder of tech dump"
            logger.error(log_msg)
            raise ValueError(log_msg)
        #print(self.rfDomains)

        self.startupContent = ''
        startupPath = (f"{self.projectFolder}/files/etc2/nvram/")
        list_of_files = sorted( filter( os.path.isfile,
                                glob.glob(startupPath + '*') ) )
        for thisfile in list_of_files:
            if thisfile.__contains__("startup-config") and ("bak" not in thisfile):
                try:
                    with open(thisfile, "r") as f:
                        self.startupContent += f.read()
                except FileNotFoundError:
                    log_msg = "The startup-config file was not found in the tech dump"
                    raise ValueError(log_msg)

        data = self.__getRfDomainInfo()

        #pprint(data)
        
        self.domain_df = pd.DataFrame(data)
        #create an empty location id column
        self.domain_df['parent'] = None
        #print(self.domain_df)


        # Collect AP data from tech dump
        ap_data = []
        ap_info = re.findall(r"(\w{2}\d{3,4}\s(\S{2}-){5}\S{2}.*?)!", self.startupContent, re.DOTALL)
        for ap in ap_info:

            ap = ap[0]
            with open(f'{PATH}/templates/wing_apconfig.textfsm') as f:
                ap_template = textfsm.TextFSM(f)
            data = ap_template.ParseText(ap)
            try:
                data = [dict(zip(ap_template.header, row)) for row in data][0]
            except IndexError:
                log_msg = ("Failed to parse AP template correctly")
                print('\n' + log_msg + ": check log for details. Skipping AP \nContinuing to gather data....", end='')
                logger.error(log_msg)
                logger.info("Headers are: " + ", ".join(ap_template.header))
                logger.info("Values are: " + ", ".join(data[0]))
                continue
            ap_data.append(data)
        # Check APs for additional floors

        for ap in ap_data:
            filt = self.domain_df['name'] == ap['rfdomain']
            floorList = self.domain_df.loc[filt,'floors'].values[0]
            if not isinstance(floorList, list):
                floorList = []
            if ap['floor']:
                if ap['floor'] not in floorList:
                    floorList.append(ap['floor'])
                    logger.warning(f"AP {ap['name']} in rf-domain {ap['rfdomain']} is set to floor {ap['floor']} which is not a floor configured in the rf-domain. Floor will be created in XIQ")
                else:
                    continue
            elif floorList:
                ap['floor'] = floorList[0]
                if self.APNoFloorLogging == True:
                    logger.warning(f"AP {ap['name']} in rf-domain {ap['rfdomain']} is not set to a floor. This AP will be placed on floor {floorList[0]}.")
            else:
                ap['floor'] = 'floor1'
                floorList.append(ap['floor'])
                if self.APNoFloorLogging == True:
                    logger.warning(f"AP {ap['name']} in rf-domain {ap['rfdomain']} is not set to a floor and no floors are configured in the rf-domain. Floor 'floor1' will be created in XIQ")
        #print(self.domain_df)


        # Create dataframe of AP data
        self.ap_df = pd.DataFrame(ap_data)
        #print(self.ap_df)
        
        #Create Location dictionary and validate location info
        location_df = pd.DataFrame(columns= ['type', 'name', 'parent', 'child'])
        for index,row in self.domain_df.iterrows():
            if row['name'] not in self.ap_df['rfdomain'].unique():
                logger.warning(f"No APs were found in rf-domain {row['name']}. This rf-domain will not be created in XIQ")
                continue
            if isinstance(row['floors'], list):
                location_list = row['locationTree']
                count = len(location_list)
                for i in range(count):
                    if i == count-1:
                        type = 'Site'
                    else:
                        type = 'Site Group'
                    if i == 0:
                        parent = 'Global'
                    else:
                        parent = location_list[i-1]
                    if i == len(location_list)-1:
                        child = 'rf-domain'
                    else:
                        child = location_list[i+1]
                    name = location_list[i]
                    if location_list[i] in location_df['name'].unique():
                        filt = (location_df['name'] == location_list[i])
                        matchLocation = location_df.loc[filt]
                        if len(matchLocation) == 1:
                            if child == matchLocation['child'].values[0] and parent != matchLocation['parent'].values[0]:
                                logger.warning(f"fixing locations in rf-domain {row['name']} - changing {location_list[i-1]} from {location_list[i-1]} to {matchLocation['parent'].values[0]}")
                                parent = matchLocation['parent'].values[0]
                            elif child != matchLocation['child'].values[0] and parent != matchLocation['parent'].values[0]:
                                name = f"{location_list[i]}_{location_list[i-1]}"
                                name = name.replace(" ", "")
                                if len(name) > 32:
                                    name = name[0:31]
                                logger.warning(f"Changing name of location in rf-domain {row['name']} due to the name being used for another location. New name is {name}")

                        else:
                            logger.error(f"Fatal Error with Locations in {row['name']} removing all locations for rf-domain {row['name']}")
                            row['parent'] = 'Global'
                    else:
                        temp_df = pd.DataFrame([{'type': type, 'name': name, 'parent': parent, 'child': child}])
                        location_df = pd.concat([location_df, temp_df], ignore_index=True)
                if location_list:
                    self.domain_df.loc[index,'parent'] = location_list[-1]
                else:
                    self.domain_df.loc[index,'parent'] = 'Global'

       
        
        #Build data for API calls and data for print screen
        self.wingData = {'building':[],'floors':[],'aps':[]}
        output_data = {}
        for index,row in self.domain_df.iterrows():
            if row['name'] not in self.ap_df['rfdomain'].unique():
                continue
            if isinstance(row['floors'], list):
                location_tree = []
                parent = row['parent']
                while parent != 'Global':
                    filt = location_df['name'] == parent
                    location_tree.append(parent)
                    parent = (location_df.loc[filt,'parent'].values[0])
                current_level = output_data
                for location in reversed(location_tree):
                    if location not in current_level:
                        current_level[location]={}
                    current_level=current_level[location]
                if 'BUILDINGS' not in current_level:
                    current_level['BUILDINGS'] = {}
                current_level = current_level['BUILDINGS']
                building_id = uuid.uuid4()
                building_data = {
                    "name": row['name'],
                    'address': row['address'],
                    'location_tree': list(reversed(location_tree)),
                    'country_code': row['countryCode'],
                    'building_id': str(building_id),
                    'xiq_building_id': None
                    }
                sys.stdout.flush()
                self.wingData['building'].append(building_data)
                current_level[row['name']] = {'address' : row['address'], 'FLOORS' : {}}
                current_level = current_level[row['name']]['FLOORS']
                for floor in row["floors"]:
                    floor_id = uuid.uuid4()
                    floor_data = {
                        'associated_building_id': str(building_id),
                        'db_attenuation': '15.0',
                        'environment': 'AUTO_ESTIMATE',
                        'floor_id': str(floor_id),
                        'installation_height': '14',
                        'map_name': '',
                        'map_size_height': '300',
                        'map_size_width': '300',
                        'measurement_unit': 'FEET',
                        'name': floor,
                        'xiq_floor_id': None
                        }
                    self.wingData['floors'].append(floor_data)
                    if floor not in current_level:
                        current_level[floor]={'deviceCount': 0}
                    filt = (self.ap_df['floor'] == floor) & (self.ap_df['rfdomain'] == row['name'])
                    floor_aps = self.ap_df.loc[filt]
                    # Variables used to space out APs onto floorplan
                    rangeList = [*range(0, 92, 9)] 
                    #rangeList = [*range(0, 300, 30)]
                    pageCount = 0
                    xList = []
                    yList = []    
                    for index, ap in floor_aps.iterrows():
                        # Spacing out the X,Y of the APs
                        if not yList:
                            xList = rangeList.copy()
                            yList = rangeList.copy()
                        if not xList:
                            xList = rangeList.copy()
                            yList.pop(0)
                        apX = xList[0] + pageCount
                        xList.pop(0)
                        apY = yList[0]
                        if (len(xList) == 0) and (len(yList) == 1):
                            yList.pop(0)
                            pageCount += 3
                        # AP Data
                        ap_data = {
                            'name': ap['name'],
                            'x': apX,
                            'y': apY,
                            'location_id':str(floor_id),
                            'mac': ap['macaddr'].replace("-",""),
                            'xiq_id': None
                        }
                        self.wingData['aps'].append(ap_data)
                        current_level[floor]['deviceCount'] += 1
        self.removeProjectFolder()


        return self.wingData, output_data  
                     
    def removeProjectFolder(self):
        shutil.rmtree(current_dir + '/project') 