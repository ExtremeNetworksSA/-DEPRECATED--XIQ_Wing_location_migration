# WiNG Location Migration to XIQ
### XIQ_wing_migrate.py

## Purpose
This script can be used to migrate the location hierarchy, rf-domains, and floors from WiNG to XIQ. This script will also assign APs that are configured in WiNG to the correct locations in XIQ after the locations are created. A tech-dump from the wing controller will be needed for the script. The script will parse the rf-domain data and device data using a couple files from within the tech-dump. Nothing needs to be done with the tech-dump. The script will ask for the file, just put the name of the tar.gz file (with its path).

## Information
### Needed files
The XIQ_wing_migrate.py script uses several other files. If these files are missing the script will not function.
In the same folder as the XIQ_wing_migrate.py script there should be an /app/ folder. Inside this folder should be a mapImportLogger.py, Wing_importer.py, xiq_exporter.py and another folder called /templates/. After running the script a new file 'map_importer.log will be created. The templates folder should have 2 files - wing_apconfig.textfsm and wing_rfomain.textfsm.

### Location hierarchy
The tree-node of the rf-domain will be used to build the location hierarchy. If there is not a tree-node configured in the rf-domain the rf-domain (building) will be created at the global view level in XIQ. Otherwise the rf-domain will be created as a building in the location hierarchy. 

### Rf-domains

Each rf-domain will be created as a building element in XIQ. Any floors configured in the rf-domain will be created under that building in XIQ. If there are no floors configured in the rf-domain 'floor1' will be created under that building in XIQ.

### Devices

The script will search for all devices pulled from the config in the XIQ instance logged into by the mac address. If the mac address is found within the XIQ instance the location will be updated to a floor within the assigned rf-domain of the device. If the device config contains the floor it will be placed in that floor, (the script will create that floor in the rf-domain if it doesn't exist already). If there is no floor in the device config it will be added to the first floor the script finds in the rf-domain. If the rf-domain has no floors, as stated, 'floor1' will be created and all devices added to that floor.

### Geo Coordinates

If geo coordinates are configured in the rf-domain, the script can convert them the physical addresses and assign that address to the building when creating it in XIQ. In order to do this an API call will need to be made to a third party location service at [platform.here.com](https://platform.here.com/). In order to leverage this an API token will need to be created. There is a free tier that allows up to 1000 requests per day. 
Detailed instructions on creating the API token will be added in the full document, but for now follow these steps.

1. Go to [account.here.com](http://account.here.com) and sign up for an account
2. Click the launcher on the top right of the screen and select Access Manager
3. At the top select Apps then 'Register a new app'
4. Give the app a name like 'reverse geo coords' and select 'Register'
5. Under credentials in the newly created app, select API Keys, then click 'Create API key'
6. Copy the created API key and add it between the quotes on line 17 of the XIQ_wing_migrate.py script

If there is no API token or if the geo-coordinates are not configured in the rf-domains, the buildings will be created with 'Unknown Address' in XIQ

## Running the script

When running the script a prompt will display asking for the tech-dump File
```
Please enter the Wing Tech-dump File:
```
You can enter the name of the file, including the full path. Or on a mac you can simply click and drag the file to the terminal window
> NOTE: This process can take a few minutes depending on the size of your config.

Once this process completes a message will be displayed with the collected number of rf-domains and devices.

Then you can preview what the hierarchy will look like in XIQ. You can choose to view this or not. If you view it, you will have the option to cancel the script before anything is created in XIQ.
> NOTE: if you have a large config this output can be truncated depending on how many lines your terminal window allows

Once proceeding to create in XIQ you will be asked for your XIQ login credentials.
> NOTE: you can by pass this section by entering a valid API Token to line 18 of the XIQ_wing_migrate.py script
>  - if the added token isn't valid you will see the script fail to gather location tree info with a HTTP Status Code: 401
### messages
As locations, buildings, and floors are created, messages will appear in the terminal window. If a location exists with the same name a message will be displayed that the locations was found and will be used. 
> NOTE: XIQ requires that each location and building have their own unique name. Floors within a building also have to have their own unique name.

### flags
There are 2 optional flags that can be added to the script when running.
```
--external
```
This flag will allow you to create the locations and assign the devices to locations on an XIQ account you are an external user on. After logging in with your XIQ credentials the script will give you a numeric option of each of the XIQ instances you have access to. Choose the one you would like to use.
```
--noaplog
```
This flag will suppress the log messages that are normally created when devices do not have a floor assigned to them in their config. If you typically do not assign a floor to the device the log file could fill up with warning messages about APs not being set to a floor and the script assigning them to 'floor1'.


## requirements
There are additional modules that need to be installed in order for this script to function. They are listed in the requirements.txt file and can be installed with the command 'pip install -r requirements.txt' if using pip.