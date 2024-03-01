#!/usr/bin/env python3
import logging
import os
import inspect
import sys
import json
import requests
import time
import pandas as pd
current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir) 
from requests.exceptions import HTTPError
from app.mapImportLogger import logger
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger('MapImporter.xiq_exporter')

PATH = current_dir


class XIQ:
    def __init__(self, user_name=None, password=None, token=None):
        self.URL = "https://api.extremecloudiq.com"
        self.headers = {"Accept": "application/json", "Content-Type": "application/json"}
        self.proxyDict = {
            "http": "",
            "https": ""
        }
        self.totalretries = 5
        self.locationTree_df = pd.DataFrame(columns = ['id', 'name', 'type', 'parent'])
        self.site = {}
        if token:
            self.headers["Authorization"] = "Bearer " + token
        else:
            try:
                self.__getAccessToken(user_name, password)
            except ValueError as e:
                print(e)
                raise SystemExit
            except HTTPError as e:
               print(e)
               raise SystemExit
            except:
                log_msg = "Unknown Error: Failed to generate token for XIQ"
                logger.error(log_msg)
                print(log_msg)
                raise SystemExit 

    #API CALLS
    def __setup_get_api_call(self, info, url):
        success = 0
        for count in range(1, self.totalretries):
            try:
                response = self.__get_api_call(url=url)
            except ValueError as e:
                print(f"API to {info} failed attempt {count} of {self.totalretries} with {e}")
            except Exception as e:
                print(f"API to {info} failed with {e}")
                print('script is exiting...')
                raise SystemExit
            except:
                print(f"API to {info} failed attempt {count} of {self.totalretries} with unknown API error")
            else:
                success = 1
                break
        if success != 1:
            print("failed to {}. Cannot continue to import".format(info))
            print("exiting script...")
            raise SystemExit
        if 'error' in response:
            if response['error_mssage']:
                log_msg = (f"Status Code {response['error_id']}: {response['error_message']}")
                logger.error(log_msg)
                print(f"API Failed {info} with reason: {log_msg}")
                print("Script is exiting...")
                raise SystemExit
        return response
        
    def __setup_post_api_call(self, info, url, payload, res=True):
        success = 0
        for count in range(1, self.totalretries):
            try:
                response = self.__post_api_call(url=url, payload=payload, res=res)
            except ValueError as e:
                print(f"API to {info} failed attempt {count} of {self.totalretries} with {e}")
            except Exception as e:
                print(f"API to {info} failed with {e}")
                print('script is exiting...')
                raise SystemExit
            except:
                print(f"API to {info} failed attempt {count} of {self.totalretries} with unknown API error")
            else:
                success = 1
                break
        if success != 1:
            print("failed {}. Cannot continue to import".format(info))
            print("exiting script...")
            raise SystemExit
        if 'error' in response:
            if response['error_mssage']:
                if 'duplicate' in response['error_message']:
                    return response
                else:
                    log_msg = (f"Status Code {response['error_id']}: {response['error_message']}")
                    logger.error(log_msg)
                    print(f"API Failed {info} with reason: {log_msg}")
                    print("Script is exiting...")
                    raise SystemExit
        return response
    
    def __setup_put_api_call(self, info, url, payload=''):
        success = 0
        for count in range(1, self.totalretries):
            try:
                if payload:
                    self.__put_api_call(url=url, payload=payload)
                else:
                    self.__put_api_call(url=url)
            except ValueError as e:
                print(f"API to {info} failed attempt {count} of {self.totalretries} with {e}")
            except Exception as e:
                print(f"API to {info} failed with {e}")
                print('script is exiting...')
                raise SystemExit
            except:
                print(f"API to {info} failed attempt {count} of {self.totalretries} with unknown API error")
            else:
                success = 1
                break
        if success != 1:
            print("failed to {}. Cannot continue to import".format(info))
            print("exiting script...")
            raise SystemExit
        
        return 'Success'


    def __get_api_call(self, url):
        try:
            response = requests.get(url, headers= self.headers, verify=False, proxies=self.proxyDict)
        except HTTPError as http_err:
            logger.error(f'HTTP error occurred: {http_err} - on API {url}')
            raise ValueError(f'HTTP error occurred: {http_err}') 
        if response is None:
            log_msg = "ERROR: No response received from XIQ!"
            logger.error(log_msg)
            raise ValueError(log_msg)
        if response.status_code != 200:
            log_msg = f"Error - HTTP Status Code: {str(response.status_code)}"
            logger.error(f"{log_msg}")
            try:
                data = response.json()
            except json.JSONDecodeError:
                logger.warning(f"\t\t{response.text}")
            else:
                if 'error_message' in data:
                    logger.warning(f"\t\t{data['error_message']}")
                    raise ValueError(log_msg)
            raise ValueError(log_msg) 
        try:
            data = response.json()
        except json.JSONDecodeError:
            logger.error(f"Unable to parse json data - {url} - HTTP Status Code: {str(response.status_code)}")
            raise ValueError("Unable to parse the data from json, script cannot proceed")
        return data

    def __post_api_call(self, url, payload, res=True):
        try:
            response = requests.post(url, headers= self.headers, data=payload, verify=False, proxies=self.proxyDict)
        except HTTPError as http_err:
            logger.error(f'HTTP error occurred: {http_err} - on API {url}')
            raise ValueError(f'HTTP error occurred: {http_err}') 
        if response is None:
            log_msg = "ERROR: No response received from XIQ!"
            logger.error(log_msg)
            raise ValueError(log_msg)
        if response.status_code == 202:
            return "Success"
        elif response.status_code == 201:
            return "Success"
        elif response.status_code != 200:
            log_msg = f"Error - HTTP Status Code: {str(response.status_code)}"
            logger.error(f"{log_msg}")
            try:
                data = response.json()
            except json.JSONDecodeError:
                logger.warning(f"\t\t{response.text}")
            else:
                if 'error_message' in data:
                    if 'duplicate' in data['error_message']:
                        return data
                    logger.warning(f"\t\t{data['error_message']}")
                    raise Exception(data['error_message'])
            raise ValueError(log_msg)
        else:
            if res:
                try:
                    data = response.json()
                except json.JSONDecodeError:
                    logger.error(f"Unable to parse json data - {url} - HTTP Status Code: {str(response.status_code)}")
                    raise ValueError("Unable to parse the data from json, script cannot proceed")
                return data
            else:
                return "Success" 
    
    def __put_api_call(self, url, payload=''):
        try:
            if payload:
                response = requests.put(url, headers= self.headers, data=payload, verify=False, proxies=self.proxyDict)
            else:
                response = requests.put(url, headers= self.headers, verify=False, proxies=self.proxyDict)
        except HTTPError as http_err:
            logger.error(f'HTTP error occurred: {http_err} - on API {url}')
            raise ValueError(f'HTTP error occurred: {http_err}') 
        if response is None:
            log_msg = "ERROR: No response received from XIQ!"
            logger.error(log_msg)
            raise ValueError(log_msg)
        if response.status_code != 200:
            log_msg = f"Error - HTTP Status Code: {str(response.status_code)}"
            logger.error(f"{log_msg}")
            logger.warning(f"\t\t{response}")
            try:
                data = response.json()
            except json.JSONDecodeError:
                logger.error(f"Unable to parse json data - {url} - HTTP Status Code: {str(response.status_code)}")
                raise ValueError("Unable to parse the data from json, script cannot proceed")
            else:
                if 'error_message' in data:
                    logger.warning(f"\t\t{data['error_message']}")
                    raise Exception(data['error_message'])
                raise ValueError(log_msg)
        else:
            return response.status_code

    def __image_api_call(self, url, files):
        headers = self.headers.copy()
        del headers['Content-Type']
        try:
            response = requests.post(url, headers= headers, files=files, verify=False, proxies=self.proxyDict)
        except HTTPError as http_err:
            logger.error(f'HTTP error occurred: {http_err} - on API {url}')
            raise ValueError(f'HTTP error occurred: {http_err}') 
        if response is None:
            log_msg = "ERROR: No response received from XIQ!"
            logger.error(log_msg)
            raise ValueError(log_msg)
        if response.status_code != 200:
            log_msg = f"Error - HTTP Status Code: {str(response.status_code)}"
            logger.error(f"{log_msg}")
            try:
                data = response.json()
            except json.JSONDecodeError:
                logger.warning(f"\t\t{response.text}")
            else:
                if 'error_message' in data:
                    logger.warning(f"\t\t{data['error_message']}")
                    raise Exception(data['error_message'])
            raise ValueError(log_msg)
        return 1

    def __getAccessToken(self, user_name, password):
        info = "get XIQ token"
        success = 0
        url = self.URL + "/login"
        payload = json.dumps({"username": user_name, "password": password})
        for count in range(1, self.totalretries):
            try:
                data = self.__post_api_call(url=url,payload=payload)
            except ValueError as e:
                print(f"API to {info} failed attempt {count} of {self.totalretries} with {e}")
            except Exception as e:
                print(f"API to {info} failed with {e}")
                print('script is exiting...')
                raise SystemExit
            except:
                print(f"API to {info} failed attempt {count} of {self.totalretries} with unknown API error")
            else:
                success = 1
                break
        if success != 1:
            print("failed to get XIQ token. Cannot continue to import")
            print("exiting script...")
            raise SystemExit
        
        if "access_token" in data:
            #print("Logged in and Got access token: " + data["access_token"])
            self.headers["Authorization"] = "Bearer " + data["access_token"]
            return 0

        else:
            log_msg = "Unknown Error: Unable to gain access token for XIQ"
            logger.warning(log_msg)
            raise ValueError(log_msg)
    
    # EXTERNAL ACCOUNTS
    def __getVIQInfo(self):
        info="get current VIQ name"
        success = 0
        url = "{}/account/home".format(self.URL)
        for count in range(1, self.totalretries):
            try:
                data = self.__get_api_call(url=url)
            except ValueError as e:
                print(f"API to {info} failed attempt {count} of {self.totalretries} with {e}")
            except:
                print(f"API to {info} failed attempt {count} of {self.totalretries} with unknown API error")
            else:
                success = 1
                break
        if success != 1:
            print(f"Failed to {info}")
            return 1
            
        else:
            self.viqName = data['name']
            self.viqID = data['id']

    ## EXTERNAL FUNCTION

    #ACCOUNT SWITCH
    def selectManagedAccount(self):
        self.__getVIQInfo()
        info="gather accessible external XIQ accounts"
        success = 0
        url = "{}/account/external".format(self.URL)
        for count in range(1, self.totalretries):
            try:
                data = self.__get_api_call(url=url)
            except ValueError as e:
                print(f"API to {info} failed attempt {count} of {self.totalretries} with {e}")
            except:
                print(f"API to {info} failed attempt {count} of {self.totalretries} with unknown API error")
            else:
                success = 1
                break
        if success != 1:
            print(f"Failed to {info}")
            return 1
            
        else:
            return(data, self.viqName)


    def switchAccount(self, viqID, viqName):
        info=f"switch to external account {viqName}"
        success = 0
        url = "{}/account/:switch?id={}".format(self.URL,viqID)
        payload = ''
        for count in range(1, self.totalretries):
            try:
                data = self.__post_api_call(url=url, payload=payload)
            except ValueError as e:
                print(f"API to {info} failed attempt {count} of {self.totalretries} with {e}")
            except Exception as e:
                print(f"API to {info} failed with {e}")
                print('script is exiting...')
                raise SystemExit
            except:
                print(f"API to {info} failed attempt {count} of {self.totalretries} with unknown API error")
            else:
                success = 1
                break
        if success != 1:
            print("failed to get XIQ token to {}. Cannot continue to import".format(info))
            print("exiting script...")
            raise SystemExit
        
        if "access_token" in data:
            #print("Logged in and Got access token: " + data["access_token"])
            self.headers["Authorization"] = "Bearer " + data["access_token"]
            self.__getVIQInfo()
            if viqName != self.viqName:
                logger.error(f"Failed to switch external accounts. Script attempted to switch to {viqName} but is still in {self.viqName}")
                print("Failed to switch to external account!!")
                print("Script is exiting...")
                raise SystemExit
            return 0

        else:
            log_msg = "Unknown Error: Unable to gain access token for XIQ"
            logger.warning(log_msg)
            raise ValueError(log_msg) 
        

    # LOCATIONS

    def gatherLocations(self):
        info=f"gather global location"
        url = "{}/locations/tree?expandChildren=false".format(self.URL)
        response = self.__setup_get_api_call(info,url)
        for location in response:
            global_id = location['id']
            url = "{}/locations/tree?parentId={}&expandChildren=false".format(self.URL,global_id)
            child_response = self.__setup_get_api_call(info,url)
            location['children'] = child_response
        return response
    
    def gatherChildren(self, loc_id):
        info=f"gather global location"
        url = "{}/locations/tree?parentId={}&expandChildren=false".format(self.URL,loc_id)
        child_response = self.__setup_get_api_call(info,url)
        return child_response

    def createLocation(self, location_name, data):
        info=f"create location {location_name}"
        url = "{}/locations".format(self.URL)
        payload = json.dumps(data)
        response = self.__setup_post_api_call(info,url,payload)
        if 'error_message' in response:
            return 'Duplicate_Name'
        return response['id']
    
    #SITES
    def checkSite(self,name):
        site_id = 0
        found = False
        update = False
        info = f"check for site {name}"
        url = f"{self.URL}/locations/site?name={name}"
        response = self.__setup_get_api_call(info,url)
        if 'total_count' in response:
            for site in response['data']:
                if name == site['name']:
                    if 'country_code' not in site:
                        update = True
                        self.site = site
                    elif site['country_code'] == 0:
                        update = True
                        self.site = site
                    site_id = site['id']
                    found = True
                    break
        return found, update, site_id
     
    def createSite(self, site_name, data):
        info=f"create site {site_name}"
        url = "{}/locations/site".format(self.URL)
        payload = json.dumps(data)
        response = self.__setup_post_api_call(info,url,payload)
        if 'error_message' in response:
            return 'Duplicate_Name'
        return response['id']
    
    def updateSite(self, site_name, country_code):
        info=f"update site {site_name}"
        if site_name != self.site['name']:
            log_msg = f"Site {site_name} was passed to be updated but doesn't match site data {self.site['name']}"
            logger.error(log_msg)
            print(log_msg)
            print('script is exiting...')
            raise SystemExit
        else:
            site_id = self.site['id']
            url = "{}/locations/site/{}".format(self.URL, str(site_id))
            self.site['country_code'] = country_code
            del self.site['create_time']
            del self.site['update_time']
            del self.site['org_id']
            del self.site['unique_name']
            del self.site['type']
            del self.site['id']
            if 'address' in self.site:
                del self.site['address']
            payload = json.dumps(self.site)
            response = self.__setup_put_api_call(info, url, payload=payload)
            return site_id

    #BUILDINGS
    def checkBuilding(self, name):
        building_id = 0
        found = False
        info = f"check for building {name}"
        url = f"{self.URL}/locations/building?name={name}"
        response = self.__setup_get_api_call(info,url)
        if 'total_count' in response:      
            for building in response['data']:
                if name == building['name']:
                    building_id = building['id']
                    found = True
                    break
            
        return found, building_id



    def createBuilding(self, data):
        info=f"create building {data['name']}"
        url = "{}/locations/building".format(self.URL)
        payload = json.dumps(data)
        response = self.__setup_post_api_call(info, url, payload)
        if 'error_message' in response:
            print(f"API to {info} failed with {response['error_message']}")
            print('script is exiting...')
            raise SystemExit
        return response['id']

    #FLOORS
    def uploadFloorplan(self, filename):
        info=f"upload {filename}"
        success = 0
        url = "{}/locations/floorplan".format(self.URL)
        filepathname = PATH + f"/images/{filename}"
        files={
            'file' : (f'{filename}', open(filepathname, 'rb'), 'image/png'),
            'type': 'image/png'
        }
        for count in range(1, self.totalretries):
            try:
                self.__image_api_call(url=url, files=files)
            except ValueError as e:
                print(f"\nAPI to {info} failed attempt {count} of {self.totalretries} with {e}")
            except Exception as e:
                print(f"\nAPI to {info} failed with {e}")
                print('script is exiting...')
                raise SystemExit
            except:
                print(f"\nAPI to {info} failed attempt {count} of {self.totalretries} with unknown API error")
            else:
                success = 1
                break
        if success != 1:
            print("\nfailed to {}. Cannot continue to import".format(info))
            print("exiting script...")
            raise SystemExit
        else:
            logger.info(f"Successfully uploaded {filename}")

    def getFloorsOfBuilding(self, rfd_name):
        floors = {}
        errors =[]
        info = "gathering floors"
        url = self.URL + '/locations/building?name=' + rfd_name
        rawList = self.__setup_get_api_call(info,url)
        if rawList['total_count'] == 0:
            error_msg = (f"No building was found with the name {rfd_name}")
            errors.append(error_msg)
        elif rawList['total_count'] > 1:
            error_msg = (f"Multiple buildings found with the name {rfd_name}")
            errors.append(error_msg)
        else:
            if len(rawList['data']) != 1:
                error_msg = (f"Multiple buildings found with the name {rfd_name}")
                errors.append(error_msg)
            else:
                floors = self._gatherFloorList(info, rawList['data'][0]['id'])
                return floors
        if errors:
            floors['errors'] = errors
        return floors

    def _gatherFloorList(self, info, bld_id):
        url = self.URL + '/locations/tree?parentId=' + str(bld_id) + '&expandChildren=false' 
        rawList = self.__setup_get_api_call(info,url)
        return rawList
    
    def checkFloor(self, name, parent_id):
        floor_id = 0
        found = False
        info = f"check for floor {name}"
        url = f"{self.URL}/locations/floor?name={name}"
        response = self.__setup_get_api_call(info,url)
        if 'total_count' in response:
            for floor in response['data']:
                if floor['parent_id'] == int(parent_id):
                    floor_id = floor['id']
                    found = True
                    break
        return found, floor_id
    
    def createFloor(self, data):
        info=f"create floor {data['name']}"
        url = "{}/locations/floor".format(self.URL)
        payload = json.dumps(data)
        response = self.__setup_post_api_call(info,url,payload)
        if 'error_message' in response:
            if 'duplicate' in response['error_message']:
                return 'Duplicate_Name'
            else:
                print(f"Error creating floor {data['name']}")
                return 0
        return response['id']

    #APS
    def collectDevices(self, pageSize):
        info = "collecting devices" 
        page = 1
        pageCount = 1
        firstCall = True

        devices = []
        while page <= pageCount:
            url = self.URL + "/devices?page=" + str(page) + "&limit=" + str(pageSize) + "&nullField=LOCATION_ID"
            rawList = self.__setup_get_api_call(info,url)
            devices = devices + rawList['data']

            if firstCall == True:
                pageCount = rawList['total_pages']
            print(f"completed page {page} of {rawList['total_pages']} collecting Devices")
            page = rawList['page'] + 1 
        return devices
    
    def changeAPLocation(self, data):
        info="set location for APs " 
        payload = json.dumps(data)
        url = f"{self.URL}/devices/location/:assign"
        response = self.__setup_post_api_call(info,url,payload=payload, res=False)
        return response

    ## CCG
    def collectCCG(self,pageSize):
        info = "collecting CCGs" 
        page = 1
        pageCount = 1
        firstCall = True

        ccg_info = []
        while page <= pageCount:
            url = self.URL + "/ccgs?page=" + str(page) + "&limit=" + str(pageSize)
            rawList = self.__setup_get_api_call(info,url)
            ccg_info = ccg_info + rawList['data']

            if firstCall == True:
                pageCount = rawList['total_pages']
            print(f"completed page {page} of {rawList['total_pages']} collecting ccg_info")
            page = rawList['page'] + 1 
        return ccg_info
