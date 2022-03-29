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

parser = argparse.ArgumentParser()
parser.add_argument('--external',action="store_true", help="Optional - adds External Account selection, to create floorplans and APs on external VIQ")
parser.add_argument('--noaplog',action="store_true", help="Optional - removes logs for APs that don't have a floor assigned")
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

def locationCreationLoop(location_tree,location_id):
    global sublocation_df
    global location_df
    for location_name in location_tree:
        if location_name not in sublocation_df['name'].unique():
            location_data = {"parent_id": f"{location_id}", "name": location_name}
            location_id = x.createLocation(location_name, location_data)
            if location_id != 0:
                log_msg = (f"Location {location_name} was successfully created.")
                location_df = pd.concat([location_df, pd.DataFrame([{'id': location_id, 'name': location_name, 'type': 'Location'}])])
                sublocation_df = pd.concat([sublocation_df, pd.DataFrame([{'id': location_id, 'name': location_name, 'type': 'Location'}])])
                sys.stdout.write(GREEN)
                sys.stdout.write(log_msg+'\n\n')
                sys.stdout.write(RESET)
                logger.info(log_msg)
            else:
                log_msg = f"Failed to create location {location_name}"
                sys.stdout.write(RED)
                sys.stdout.write(log_msg + "\n")
                sys.stdout.write(RESET)
                logger.error(log_msg)
                return ValueError("Error in location creation loop.")
        else:
            filt = location_df['name'] == location_name
            location_id = location_df.loc[filt,'id'].values[0]
            print(f"Location {location_name} was found.. id is {location_id}\n")
    return location_id
#MAIN


## Wing IMPORT
filename = str(input("Please enter the Wing Tech-dump File: ")).strip()
filename = filename.replace("\ ", " ")
filename = filename.replace("'", "")

print("Gathering Wing Data.... ", end='')
sys.stdout.flush()
x = Wing(filename, APNoFloorLogging= not args.noaplog, geoApiKey=geoApiKey)
#try:
rawData, output_preview = x.exportFile()
#except ValueError as e:
#    print("Failed")
#    sys.stdout.write(RED)
#    sys.stdout.write(e)
#    sys.stdout.write("script is exiting....\n")
#    sys.stdout.write(RESET)
#    raise SystemExit
#except:
#    log_msg = "Unknown Error opening and exporting Wing Tech-dump data"
#    print("Failed")
#    sys.stdout.write(RED)
#    sys.stdout.write(log_msg + "\n")
#    sys.stdout.write("script is exiting....\n")
#    sys.stdout.write(RESET)
#    logger.error(log_msg)
#    raise SystemExit
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

print("Enter your XIQ login credentials")
username = input("Email: ")
password = getpass.getpass("Password: ")


x = XIQ(username,password)
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

#TODO - check if this works with large location Tree   
location_df = x.gatherLocations()
filt = location_df['type'] == 'BUILDING'
building_df = location_df.loc[filt]
filt = location_df['type'] == 'Location'
sublocation_df = location_df.loc[filt]


# Check Building
if rawData['building']:
    for building in rawData['building']:
        if not any(d['associated_building_id'] == building['building_id'] for d in rawData['floors']):
            log_msg = (f"no floors were found for building {building['name']}. Skipping creation of building")
            logger.info(log_msg)
            continue
        if building['name'] in building_df['name'].unique():
            xiq_building_exist = True
            filt = location_df['name'] == building['name']
            building_id = location_df.loc[filt, 'id'].values[0]
            building['xiq_building_id'] = str(building_id)
            log_msg = (f"Building {building['name']} already exists! The Script will attempt to add Floors and APs to this building")
            logger.critical(log_msg)
            sys.stdout.write(YELLOW)
            sys.stdout.write(log_msg + "\n\n")
            sys.stdout.write(RESET)

        else:
            data = building.copy()
            filt = location_df['type'] == 'Global'
            location_id = location_df.loc[filt, 'id'].values[0]
            parent_name = location_df.loc[filt, 'name'].values[0]
            if building['location_tree']:
                try:
                    location_id = locationCreationLoop(building['location_tree'],location_id)
                except ValueError as e:
                    sys.stdout.write(YELLOW)
                    sys.stdout.write(f"{e} {building['name']} will be placed under the Global view.")
                    sys.stdout.write(RESET)
            del data['building_id']
            del data['xiq_building_id']
            if not data['address'].strip():
                data['address'] = 'Unknown Address'
            data['parent_id'] = f"{location_id}"
            building['xiq_building_id'] = x.createBuilding(data)
            if building['xiq_building_id'] != 0:
                log_msg = f"Building {building['name']} was successfully created."
                sys.stdout.write(GREEN)
                sys.stdout.write(log_msg+'\n\n')
                sys.stdout.write(RESET)
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
        continue
    filt = wing_building_df['building_id'] == floor['associated_building_id']
    xiq_building_id = wing_building_df.loc[filt, 'xiq_building_id'].values[0]
    building_name = wing_building_df.loc[filt, 'name'].values[0]
    #check if floor exists
    filt = (location_df['type'] == 'FLOOR') & (location_df['parent'] == building_name)
    floor_df = location_df.loc[filt]
    if floor['name'] in floor_df['name'].unique():
        log_msg = f"There is already a floor with the name {floor['name']} in building {building_name}"
        logger.info(log_msg)
        sys.stdout.write(YELLOW)
        sys.stdout.write(log_msg+'n')
        sys.stdout.write(RESET)
        filt = floor_df['name'] == floor['name']
        floor['xiq_floor_id'] = floor_df.loc[filt, 'id'].values[0]
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
        logger.info(log_msg)

# ADD APS TO FLOORS
wing_floor_df = pd.DataFrame(rawData['floors'])
wing_ap_df = pd.DataFrame(rawData['aps'])
# change location_id to xiq_floor_id
listOfFloors = list(wing_ap_df['location_id'].unique())
for floor_id in listOfFloors:
    filt = wing_floor_df['floor_id'] == floor_id
    xiq_id = (wing_floor_df.loc[filt,'xiq_floor_id'].values[0])
    wing_ap_df = wing_ap_df.replace({'location_id':{floor_id : str(xiq_id)}})
#get list of mac addresses
listOfMacs = list(wing_ap_df['mac'].dropna().unique())

# Batch mac addresses
displayCount = False
sizeofbatch = 100
if len(listOfMacs) > sizeofbatch:
    print("\nThis script will work in batches of 100 APs.\n")
    displayCount = True


apsToConfigure = []
for i in range(0, len(listOfMacs),sizeofbatch):
    batch = listOfMacs[i:i+sizeofbatch]
    cleanBatch = listOfMacs[i:i+sizeofbatch]
    apMacFound = False
    if displayCount == True:
        print(f"Checking for APs {i}-{i+sizeofbatch} of {len(listOfMacs)}")
    # check if they exist 
    existingAps = x.checkApsByMac(batch)
    for ap in existingAps:
        batch = list(filter(lambda a: a != ap['mac_address'], batch))
        updateApWithId(ap)
    foundAPs = [i for i in cleanBatch if i not in batch]
    apsToConfigure.extend(foundAPs)
    for ap_mac in batch:
        filt = wing_ap_df['mac'] == ap_mac
        offline_ap = wing_ap_df.loc[filt,'name'].values[0]
        logger.error(f"Device {offline_ap} ({ap_mac}) was not found in XIQ")

if apsToConfigure:
    print(f"Starting to move {len(apsToConfigure)} out of the {len(rawData['aps'])} APs that were found in this XIQ instance.")
    for ap_mac in apsToConfigure:
        filt = wing_ap_df['mac'] == ap_mac
        ap_df = wing_ap_df[filt]
        data = {
            "location_id" : ap_df['location_id'].values[0],
            "x" : int(ap_df['x'].values[0]),
            "y" : int(ap_df['y'].values[0]),
            "latitude": 0,
            "longitude": 0
        }
        response = x.changeAPLocation(ap_df['xiq_id'].values[0], data)
        if response != "Success":
            log_msg = (f"Failed to set location of {ap_df['xiq_id'].values[0]}")
            sys.stdout.write(RED)
            sys.stdout.write(log_msg + "\n")
            sys.stdout.write(RESET)
            logging.error(log_msg)
        else:
            logger.info(f"Set location for {ap_df['name'].values[0]}")
    print("Finished moving APs and placing them")
else:
    sys.stdout.write(YELLOW)
    sys.stdout.write("No AP mac addresses were found in the XIQ instance.\n")
    sys.stdout.write(RESET)
#pprint(rawData)