#!/usr/bin/env python
import logging
import argparse
import sys
import os
import sys
import inspect
import getpass
import json
import pandas as pd
from app.Wing_importer import Wing
from app.mapImportLogger import logger
from app.xiq_exporter import XIQ

current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
logger = logging.getLogger('MapImporter.Main')

geoApiKey = ''
XIQ_API_token = ''

pageSize = '100'

parser = argparse.ArgumentParser()
parser.add_argument('--external',action="store_true", help="Optional - adds External Account selection, to create floorplans and APs on external VIQ")
parser.add_argument('--noaplog',action="store_true", help="Optional - removes logs for APs that don't have a floor assigned")
parser.add_argument('--nogeolog',action="store_true", help="Optional - removes logs for no GEO API key when creating locations")
args = parser.parse_args()

PATH = current_dir

# Git Shell Coloring - https://gist.github.com/vratiu/9780109
RED   = "\033[1;31m"  
BLUE  = "\033[1;34m"
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
RESET = "\033[0;0m"

def yesNoLoop(question):
    validResponse = False
    while validResponse != True:
        response = input(f"{question} (y/n) ").lower()
        if response =='n' or response == 'no':
            response = 'n'
            validResponse = True
        elif response == 'y' or response == 'yes':
            response = 'y'
            validResponse = True
        elif response == 'q' or response == 'quit':
            sys.stdout.write(RED)
            sys.stdout.write("script is exiting....\n")
            sys.stdout.write(RESET)
            raise SystemExit
    return response

def updateApWithId(ap):
    global wing_ap_df
    filt = wing_ap_df['mac'] == ap['mac_address']
    wing_ap_df.loc[filt,'xiq_id'] = ap['id']

def checkNameLength(name, type):
    while len(name) > 32:
        sys.stdout.write(YELLOW)
        sys.stdout.write(f"'{name}' is longer than 32 characters allowed for a name.\n")
        sys.stdout.write(RESET)
        name = input(f"Please enter a new name for the {type} that is less than 32 characters: ")
    return name

def createSiteLoop(parent_id, site_name, country_code):
    valid_site = False
    while not valid_site:
        site_name = checkNameLength(site_name, 'Site')
        data = {"parent_id": parent_id,
                "name": site_name,
                "country_code": country_code
                }
        site_id = x.createSite(site_name,data)
        if site_id != 'Duplicate_Name':
            valid_site = True
        else:
            print(f"{site_name} already exists. XIQ requires a unique name.")
            site_name = input(f"Please enter a name for the site: ")
    log_msg = f"Site {site_name} was created successfully."
    sys.stdout.write(GREEN)
    sys.stdout.write(log_msg + "\n\n")
    sys.stdout.write(RESET)
    sys.stdout.flush()
    logger.info(log_msg)
    return site_id

def createLocLoop(parent_id, loc_name):
    valid_loc = False
    while not valid_loc:
        loc_name = checkNameLength(loc_name, 'Site Group')
        data = {"parent_id": parent_id,
                "name": loc_name}
        loc_id = x.createLocation(loc_name,data)
        if loc_id != 'Duplicate_Name':
            valid_loc = True
        else:
            print(f"{loc_name} already exists. XIQ requires a unique name.")
            loc_name = input(f"Please enter a name for the Site Group: ")
    log_msg = f"Site Group {loc_name} was created successfully."
    sys.stdout.write(GREEN)
    sys.stdout.write(log_msg + "\n\n")
    sys.stdout.write(RESET)
    sys.stdout.flush()
    logger.info(log_msg)
    return loc_id

def locationCreationLoop(location_tree, country_code):
    if len(location_tree) == 1:
        if not any(d['name'] == location_tree[0] for d in global_location_dic[0]['children']):
            global_site_id = global_location_dic[0]['id']
            site_name = location_tree[0]
            site_id = createSiteLoop(global_site_id, site_name, country_code)
            return site_id
        else:
            for location in global_location_dic[0]['children']:
                if location['name'] == location_tree[0]:
                    if location['type'] != 'SITE':
                        print(f"{location_tree[0]} already exists as a {location['type']}. XIQ requires a building to be part of a site. ")
                        site_name = input(f"Please enter a new name for the site: ")
                        site_group_id = location['id']
                        site_id = createSiteLoop(site_group_id, site_name, country_code)
                        return site_id
                    else:
                        site_id = location['id']
                        print(f"found site {location['name']} - {site_id}")
                        return site_id
    else:
        count = len(location_tree)
        site_number = count -1
        loc_id = global_location_dic[0]['id']
        children = global_location_dic[0]['children']
        for i in range(0, count,1):
            if i == site_number:
                site_id = createSiteLoop(loc_id, location_tree[i], country_code)
            else:
                if any(d['name'] == location_tree[i] for d in children):
                    parent_dir = next(item for item in children if item["name"] == location_tree[i] )
                    if parent_dir['type'] != "Site_Group":
                        print(f"{parent_dir['name']} already exists, but it is not a Site Group!")
                        loc_id = createLocLoop(loc_id, location_tree[i])
                    else:
                        print(f"Location {parent_dir['name']} was found in XIQ.")
                        children = x.gatherChildren(parent_dir['id'])
                        loc_id = parent_dir['id']
                else:
                    loc_id = createLocLoop(loc_id, location_tree[i])
        return site_id


    
#MAIN


## Wing IMPORT
filename = str(input("Please enter the Wing Tech-dump File: ")).strip()
filename = filename.replace("\\ ", " ")
filename = filename.replace("'", "")

print("Gathering Wing Data.... ", end='')
sys.stdout.flush()
x = Wing(filename, APNoFloorLogging= not args.noaplog, GEOAPILogging= not args.nogeolog, geoApiKey=geoApiKey)
try:
    rawData, output_preview = x.exportFile()
except ValueError as e:
    print("Failed")
    sys.stdout.write(RED)
    sys.stdout.write(e)
    sys.stdout.write("script is exiting....\n")
    sys.stdout.write(RESET)
    raise SystemExit
except:
    log_msg = "Unknown Error opening and exporting Wing Tech-dump data"
    print("Failed")
    sys.stdout.write(RED)
    sys.stdout.write(log_msg + "\n")
    sys.stdout.write("script is exiting....\n")
    sys.stdout.write(RESET)
    logger.error(log_msg)
    raise SystemExit
print("Complete\n")

#pprint(rawData)
#print("\n\n")

print(f"Found {len(rawData['building'])} rf-domains with {len(rawData['aps'])} APs in them.\n")
preview = yesNoLoop("Would you like to preview the data gathered from Wing and how it will be uploaded to XIQ?")
if preview == 'y':
    print(json.dumps(output_preview, indent=4, sort_keys=True))
    continueScript = yesNoLoop("Would you like to continue and create these locations in XIQ?")
    if continueScript == 'n':
        sys.stdout.write(RED)
        sys.stdout.write("script is exiting....\n")
        sys.stdout.write(RESET)
        raise SystemExit

## XIQ EXPORT
if XIQ_API_token:
    x = XIQ(token=XIQ_API_token)
else:
    print("Enter your XIQ login credentials")
    username = input("Email: ")
    password = getpass.getpass("Password: ")
    x = XIQ(user_name=username,password = password)
#OPTIONAL - use externally managed XIQ account
if args.external:
    accounts, viqName = x.selectManagedAccount()
    if accounts == 1:
        validResponse = False
        while validResponse != True:
            response = input("No External accounts found. Would you like to import data to your network?")
            if response == 'y':
                validResponse = True
            elif response =='n':
                sys.stdout.write(RED)
                sys.stdout.write("script is exiting....\n")
                sys.stdout.write(RESET)
                raise SystemExit
    elif accounts:
        validResponse = False
        while validResponse != True:
            print("\nWhich VIQ would you like to import the floor plan and APs too?")
            accounts_df = pd.DataFrame(accounts)
            count = 0
            for df_id, viq_info in accounts_df.iterrows():
                print(f"   {df_id}. {viq_info['name']}")
                count = df_id
            print(f"   {count+1}. {viqName} (This is Your main account)\n")
            selection = input(f"Please enter 0 - {count+1}: ")
            try:
                selection = int(selection)
            except:
                sys.stdout.write(YELLOW)
                sys.stdout.write("Please enter a valid response!!")
                sys.stdout.write(RESET)
                continue
            if 0 <= selection <= count+1:
                validResponse = True
                if selection != count+1:
                    newViqID = (accounts_df.loc[int(selection),'id'])
                    newViqName = (accounts_df.loc[int(selection),'name'])
                    x.switchAccount(newViqID, newViqName)

xiq_building_exist = False
print("Starting to collect locations... ", end='')
sys.stdout.flush()
global_location_dic = x.gatherLocations()
print("Complete")
sys.stdout.flush()

# Check Building
if rawData['building']:
    for building in rawData['building']:
        if not any(d['associated_building_id'] == building['building_id'] for d in rawData['floors']):
            log_msg = (f"no floors were found for building {building['name']}. Skipping creation of building")
            logger.info(log_msg)
            continue
        
        # Check if building exists
        xiq_building_exist, building_id = x.checkBuilding(building['name'])
        if xiq_building_exist:
            building['xiq_building_id'] = str(building_id)
            log_msg = (f"Building {building['name']} already exists! The Script will attempt to add Floors and APs to this building")
            logger.critical(log_msg)
            sys.stdout.write(YELLOW)
            sys.stdout.write(log_msg + "\n\n")
            sys.stdout.write(RESET)
            sys.stdout.flush()
        else:
            # Check if site exists
            site_name = building['location_tree'][-1]
            xiq_site_exist, xiq_site_update, site_id = x.checkSite(site_name)
            if xiq_site_exist:
                if xiq_site_update:
                    site_id = x.updateSite(site_name, building['country_code'])
                    log_msg = f"Site {site_name} is missing required country code, updated site with country code {building['country_code']}\n"
                    logger.info(log_msg)
                    sys.stdout.write(YELLOW)
                    sys.stdout.write(log_msg)
                    sys.stdout.write(RESET)
                data = building.copy()
                del data['building_id']
                del data['country_code']
                del data['xiq_building_id']
                if not data['address']:
                    data['address'] = {
                            "address": "Unknown",
                            "city": "Unknown",
                            "state": "Unknown",
                            "postal_code": "Unknown"
                        }
                data['parent_id'] = f"{site_id}"
                building['xiq_building_id'] = x.createBuilding(data)
                if building['xiq_building_id'] != 0:
                    log_msg = f"Building {building['name']} was successfully created."
                    sys.stdout.write(GREEN)
                    sys.stdout.write(log_msg+'\n\n')
                    sys.stdout.write(RESET)
                    sys.stdout.flush()
                    logger.info(log_msg)
            else:
                # Check/create hierarchy    
                site_id = locationCreationLoop(building['location_tree'],building['country_code'])  
                # Create Building 
                data = building.copy()
                del data['building_id']
                del data['xiq_building_id']
                del data['country_code']
                if not data['address']:
                    data['address'] = {
                            "address": "Unknown",
                            "city": "Unknown",
                            "state": "Unknown",
                            "postal_code": "Unknown"
                        }
                data['parent_id'] = f"{site_id}"
                building['xiq_building_id'] = x.createBuilding(data)
                if building['xiq_building_id'] != 0:
                    log_msg = f"Building {building['name']} was successfully created."
                    sys.stdout.write(GREEN)
                    sys.stdout.write(log_msg+'\n\n')
                    sys.stdout.write(RESET)
                    sys.stdout.flush()
                    logger.info(log_msg)


# Create Floor(s)
wing_building_df = pd.DataFrame(rawData['building'])
for floor in rawData['floors']:
    if floor['associated_building_id'] == None:
        log_msg = f"Floor '{floor['name']}' is not associated with the buildings in Wing so it will be skipped."
        logger.warning(log_msg)
        sys.stdout.write(YELLOW)
        sys.stdout.write(log_msg+'n')
        sys.stdout.write(RESET)
        sys.stdout.flush()
        continue
    filt = wing_building_df['building_id'] == floor['associated_building_id']
    xiq_building_id = wing_building_df.loc[filt, 'xiq_building_id'].values[0]
    building_name = wing_building_df.loc[filt, 'name'].values[0]
    #check if floor exists
    xiq_floor_exist, floor_id = x.checkFloor(floor['name'], xiq_building_id)
    if xiq_floor_exist:
        floor['xiq_floor_id'] = floor_id
        log_msg = f"There is already a floor with the name {floor['name']} in building {building_name}"
        logger.critical(log_msg)
        sys.stdout.write(YELLOW)
        sys.stdout.write(log_msg + "\n")
        sys.stdout.write(RESET)
        sys.stdout.flush()
        continue
    data = floor.copy()
    del data['associated_building_id']
    del data['floor_id']
    del data['xiq_floor_id']
    data['parent_id'] = str(xiq_building_id)
    floor['xiq_floor_id'] = x.createFloor(data)
    if floor['xiq_floor_id'] != 0:
        log_msg = (f"Floor {floor['name']} was successfully created in building {building_name}.")
        sys.stdout.write(GREEN)
        sys.stdout.write(log_msg+'\n\n')
        sys.stdout.write(RESET)
        sys.stdout.flush()
        logger.info(log_msg)


print("Collecting Devices...")
# Get AP info from tech Dump
wing_floor_df = pd.DataFrame(rawData['floors'])
wing_floor_df.set_index('xiq_floor_id',inplace=True)
wing_ap_df = pd.DataFrame(rawData['aps'])

# change location_id to xiq_floor_id
listOfFloors = list(wing_ap_df['location_id'].unique())
for floor_id in listOfFloors:
    filt = wing_floor_df['floor_id'] == floor_id
    xiq_id = (wing_floor_df.loc[filt].index[0])
    wing_ap_df = wing_ap_df.replace({'location_id':{floor_id : str(xiq_id)}})

# Get AP info from XIQ
device_data = x.collectDevices(pageSize)
device_df = pd.DataFrame(device_data)
if len(device_df.index) == 0:
    print("\nNo devices were found without locations set")
    print("script is exiting...")
    raise SystemExit
device_df.set_index('id',inplace=True)
print(f"\nFound {len(device_df.index)} Devices without locations")



print("Collecting CCGs...")
## Collect CCGs
ccg_data = x.collectCCG(pageSize)
#pp(ccg_data)
ccg_df = pd.DataFrame(columns = ['device_id', 'ccg_id', 'ccg_name'])
for ccg in ccg_data:
    if ccg['device_ids']:
        for device_id in ccg['device_ids']:
            ccg_df = pd.concat([ccg_df,pd.DataFrame([{'device_id': device_id, 'ccg_id': ccg['id'], 'ccg_name': ccg['name']}])])
#ccg_df = pd.DataFrame(ccg_data)
ccg_df.set_index('device_id',inplace=True)

set_location = {}
for device_id in device_df.index.tolist():
    if device_df.loc[device_id,'hostname'] in wing_ap_df['name'].unique():
        sys.stdout.write(RED)
        if device_id not in ccg_df.index.tolist():
            log_msg = (f"device {device_df.loc[device_id,'hostname']} is not associated with a Cloud Config Group!!")
            logger.critical(log_msg)
            print(log_msg)
        else:
            ccg_name = ccg_df.loc[device_id, 'ccg_name']
            if not isinstance(ccg_name, str):
                log_msg = (f"Device {device_df.loc[device_id,'hostname']} is in multiple Cloud Config Groups!!")
                logger.critical(log_msg)
                print(log_msg)
            else:
                if "RFD-" not in ccg_name:
                    log_msg = (f"Device {device_df.loc[device_id,'hostname']} is in CCG '{ccg_name}' which is not an WiNG RFD created CCG!!")
                    logger.critical(log_msg)
                    print(log_msg)
                else:
                    rfd_name = ccg_name.replace("RFD-","")
                    rfd_floor = x.getFloorsOfBuilding(rfd_name)
                    if 'errors' in rfd_floor:
                        errors = ", ".join(rfd_floor['errors'])
                        log_msg = (f"Can't move device {device_df.loc[device_id,'hostname']}. {errors}")
                        logger.critical(log_msg)
                        print(log_msg)
                    elif len(rfd_floor) == 0:
                        log_msg = (f"Can't move device {device_df.loc[device_id,'hostname']}. There is not a building with the name '{rfd_name}'!!")
                        logger.critical(log_msg)
                        print(log_msg)
                    else:
                        sys.stdout.write(GREEN)
                        if device_df.loc[device_id,'hostname'] in wing_ap_df['name'].unique():
                            filt = wing_ap_df['name'] == device_df.loc[device_id,'hostname']
                            floor_id = wing_ap_df.loc[filt,'location_id'].values[0]
                            floor = {'id': floor_id, "name": wing_floor_df.loc[int(floor_id),'name']}
                        else:
                            floor = rfd_floor[-1]  
                        log_msg = (f"Device {device_df.loc[device_id,'hostname']} will be added to {rfd_name} on floor '{floor['name']}'")
                        logger.info(log_msg)
                        print(log_msg)
                        if rfd_name not in set_location:
                            set_location[rfd_name] = {"devices":{"ids":[device_id]},"device_location":{"location_id":floor['id'],"x":0,"y":0,"latitude":0,"longitude":0}}
                        else:
                            set_location[rfd_name]["devices"]["ids"].append(device_id)
    else:
        sys.stdout.write(YELLOW)
        log_msg = f"Device {device_df.loc[device_id,'hostname']} has no location set but was not found in this Tech Dump."
        logger.warning(log_msg)
        print(log_msg)

    sys.stdout.write(RESET)

move_device_count = 0
for rfd in set_location:
    print(f"Moving APs to {rfd}...", end="")
    response = x.changeAPLocation(set_location[rfd])
    print(response)
    device_count = len(set_location[rfd]['devices'])
    print(f"Moved {device_count} APs to {rfd}")
    move_device_count += device_count

print(f"\n{move_device_count} out of {len(device_df.index)} were moved to the correct locations.")