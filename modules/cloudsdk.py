#!/usr/bin/python3

import sys
import os
import time
import http.client
import json
import csv
from datetime import datetime, timedelta
sys.path.append('config/')
CLOUD_CONFIG = "config/clouds.json"
CRED_CONFIG  = "config/PRIV-creds.json"
CACHE_CONFIG = "config/PRIV-auth-cache.json"
GET_LIMIT    = 75
CACHE_TIME   = 120

class API:
    # Make an API call
    def api_call(self, svc, method, uri, payload = {}, headers = None):
        if (svc not in self.cloud_svcs):
            raise Exception("[cloudsdk] api_call Error: svc \"%s\" is unknown" % svc)
    
        conn = http.client.HTTPSConnection(self.cloud_svcs[svc]["host"], self.cloud_svcs[svc]["port"])
        if (headers == None):
            headers = self.headers
    
        conn.request(method.upper(), uri, json.dumps(payload), headers)
        res = conn.getresponse()
        return json.loads(res.read())

    # Init CloudSDK API class
    def __init__(self, deployment = "DF", verbose = True):
        self.cloud_conf = {}
        self.cloud_svcs = {}
        self.headers    = { 'Content-Type': 'application/json' }

        # Load cloud config
        if (not os.path.exists(CLOUD_CONFIG)):
            raise Exception("[cloudsdk] Error: file %s not found" % CLOUD_CONFIG)
        f = open(CLOUD_CONFIG)
        cloud_conf = json.load(f)
        f.close()
    
        # Confirm deployment provided is known
        deployment = deployment.upper()
        if (deployment not in cloud_conf):
            raise Exception("[cloudsdk] Error: deployment \"%s\" not found in %s" % (deployment, CLOUD_CONFIG))
        self.deployment = deployment
        self.cloud_svcs = cloud_conf[deployment]
    
        # Get Auth Token
        token = None
        auth_cache = {}
        if (os.path.exists(CACHE_CONFIG)):
            # try to load from cache
            f = open(CACHE_CONFIG)
            auth_cache = json.load(f)
            f.close()
            if (self.deployment in auth_cache):
                token = auth_cache[self.deployment]
    
        if (token == None):
            # Load login credentials
            if (not os.path.exists(CRED_CONFIG)):
                raise Exception("[cloudsdk] Error: file %s not found" % CRED_CONFIG)
            f = open(CRED_CONFIG)
            creds = json.load(f)
            f.close()
            if (self.deployment not in creds):
                raise Exception("[cloudsdk] Error: credentials for \"%s\" not found in %s" % (self.deployment, CRED_CONFIG))
        
            # Login using owsec
            resp = self.api_call("owsec", "POST", "/api/v1/oauth2", creds[self.deployment])
            if (resp == None or 'access_token' not in resp):
                raise Exception("[cloudsdk] Error: login attempt to %s owsec failed" % deployment)
            token = resp['access_token']
    
            # Update cache
            auth_cache[deployment] = token
            with open(CACHE_CONFIG, "w") as outfile:
                json.dump(auth_cache, outfile)
    
        # Add token to headers
        self.headers['Authorization'] = "Bearer " + token
    
        if (verbose):
            print("[cloudsdk] %s authentication: using token '%sxxxxx..'" % (self.deployment, token[:8]))
    
    # Get current connection statistics
    def get_conn_stats(self):
        uri = "/api/v1/devices?connectionStatistics=true"
        return self.api_call("owgw", "GET", uri)

    # Get last state message of a given MAC address
    def get_device_stats(self, mac):
        uri = "/api/v1/device/%s/statistics?lastOnly=true" % (mac)
        return self.api_call("owgw", "GET", uri)
    
    # Get total device count
    def get_device_count(self):
        uri = "/api/v1/devices?countOnly=true"
        resp = self.api_call("owgw", "GET", uri)
        if ('count' not in resp):
            return -1
        return resp['count']
    
    # Get devices: must be loaded in batches if count is over 100
    def get_devices(self, limit = 100, offset = 0):
        uri = "/api/v1/devices?deviceWithStatus=true&limit=%d&offset=%d" % (limit, offset)
        resp = self.api_call("owgw", "GET", uri)
        if ('devicesWithStatus' not in resp):
            return None
        return resp['devicesWithStatus']
    
    # Get inventory count
    def get_inventory_count(self):
        uri = "/api/v1/inventory?countOnly=true"
        resp = self.api_call("owprov", "GET", uri)
        if ('count' not in resp):
            return -1
        return resp['count']
    
    # Get inventory: must be loaded in batches if count is over 100
    def get_inventory(self, limit = 100, offset = 0):
        uri = "/api/v1/inventory?withExtendedInfo=true&limit=%d&offset=%d" % (limit, offset)
        resp = self.api_call("owprov", "GET", uri)
        if ('taglist' not in resp):
            return None
        return resp['taglist']
    
    # Get venue count
    def get_venue_count(self):
        uri = "/api/v1/venue?countOnly=true"
        resp = self.api_call("owprov", "GET", uri)
        if ('count' not in resp):
            return -1
        return resp['count']
    
    # Get venues: must be loaded in batches if count is over 100
    def get_venues(self, limit = 100, offset = 0):
        uri = "/api/v1/venue?limit=%d&offset=%d" % (limit, offset)
        resp = self.api_call("owprov", "GET", uri)
        if ('venues' not in resp):
            return None
        return resp['venues']
    
    # Get entity count
    def get_entity_count(self):
        uri = "/api/v1/entity?countOnly=true"
        resp = self.api_call("owprov", "GET", uri)
        if ('count' not in resp):
            return -1
        return resp['count']
    
    # Get entities: must be loaded in batches if count is over 100
    def get_entities(self, limit = 100, offset = 0):
        uri = "/api/v1/entity?limit=%d&offset=%d" % (limit, offset)
        resp = self.api_call("owprov", "GET", uri)
        if ('entities' not in resp):
            return None
        return resp['entities']

    # Load all devices
    def load_all_devices(self, verbose = True, limit = None, no_cache = None):
        # Check if we can use cache
        if (not no_cache):
            devices = self.load_cache("Devices")
            if (devices):
                if (verbose):
                    print("[cloudsdk] -> Loaded devices cache: %d total" % len(devices))
                return devices

        if (verbose):
            print("[cloudsdk] -> Loading Device Count....", end="")
        dev_count = self.get_device_count()
        if (dev_count <= 0):
            if (verbose):
                print("%d total" % dev_count)
            return None
        if (verbose):
            print("%d total, fetching %d at a time" % (dev_count, GET_LIMIT))

        if (limit != None):
            left = limit
        else:
            left = dev_count
        left = dev_count
        offset = 0
        devices = []
        while (left > 0):
            if (verbose):
                if (left > GET_LIMIT):
                    end_cnt = offset + GET_LIMIT
                else:
                    end_cnt = offset + left
                print("[cloudsdk]    -> Fetching devices   %3d to %3d...." % ((offset+1), end_cnt), end="")
            start_tm = datetime.now()
            devs = self.get_devices(GET_LIMIT, offset)
            end_tm = datetime.now()
            if (devs == None):
                if (verbose):
                    print("failed")
                return None
            if (verbose):
                fetch_tm = (end_tm - start_tm).total_seconds()
                print("done (took %4.0f ms)" % ((fetch_tm * 1000)))
            offset += len(devs)
            left   -= len(devs)
            for d in devs:
                devices.append(d)
            if (left > 0):
                time.sleep(0.2)

        # Store in cache
        self.save_cache("Devices", devices)

        return devices

    # Load all inventory
    def load_all_inventory(self, verbose = True, limit=None):
        if (verbose):
            print("[cloudsdk] -> Loading Inventory Count....", end="")
        inv_count = self.get_inventory_count()
        if (inv_count <= 0):
            if (verbose):
                print("%d total" % inv_count)
            return None
        if (verbose):
            print("%d total, fetching %d at a time" % (inv_count, GET_LIMIT))

        if (limit != None):
            left = limit
        else:
            left = inv_count
        offset = 0
        inventory = []
        while (left > 0):
            if (verbose):
                if (left > GET_LIMIT):
                    end_cnt = offset + GET_LIMIT
                else:
                    end_cnt = offset + left
                print("[cloudsdk]    -> Fetching inventory %3d to %3d...." % ((offset+1), end_cnt), end="")
            start_tm = datetime.now()
            inv = self.get_inventory(GET_LIMIT, offset)
            end_tm = datetime.now()
            if (inv == None):
                if (verbose):
                    print("failed")
                return None
            if (verbose):
                fetch_tm = (end_tm - start_tm).total_seconds()
                print("done (took %4.0f ms)" % ((fetch_tm * 1000)))
            offset += len(inv)
            left   -= len(inv)
            for i in inv:
                inventory.append(i)
            if (left > 0):
                time.sleep(0.2)

        return inventory

    # Load all venues
    def load_all_venues(self, verbose = True, limit = None):
        if (verbose):
            print("[cloudsdk] -> Loading Venue Count....", end="")
        v_count = self.get_venue_count()
        if (v_count <= 0):
            if (verbose):
                print("%d total" % v_count)
            return None
        if (verbose):
            print("%d total, fetching %d at a time" % (v_count, GET_LIMIT))

        if (limit != None):
            left = limit
        else:
            left = v_count
        offset = 0
        venues = []
        while (left > 0):
            if (verbose):
                if (left > GET_LIMIT):
                    end_cnt = offset + GET_LIMIT
                else:
                    end_cnt = offset + left
                print("[cloudsdk]    -> Fetching venues    %3d to %3d...." % ((offset+1), end_cnt), end="")
            start_tm = datetime.now()
            vens = self.get_venues(GET_LIMIT, offset)
            end_tm = datetime.now()
            if (vens == None):
                if (verbose):
                    print("failed")
                return None
            if (verbose):
                fetch_tm = (end_tm - start_tm).total_seconds()
                print("done (took %4.0f ms)" % ((fetch_tm * 1000)))
            offset += len(vens)
            left   -= len(vens)
            for v in vens:
                venues.append(v)
            if (left > 0):
                time.sleep(0.2)

        return venues

    # Load all entities
    def load_all_entities(self, verbose = True, limit = None):
        if (verbose):
            print("[cloudsdk] -> Loading Entity Count....", end="")
        e_count = self.get_entity_count()
        if (e_count <= 0):
            if (verbose):
                print("%d total" % e_count)
            return None
        if (verbose):
            print("%d total, fetching %d at a time" % (e_count, GET_LIMIT))

        if (limit != None):
            left = limit
        else:
            left = e_count
        offset = 0
        entities = []
        while (left > 0):
            if (verbose):
                if (left > GET_LIMIT):
                    end_cnt = offset + GET_LIMIT
                else:
                    end_cnt = offset + left
                print("[cloudsdk]    -> Fetching entities  %3d to %3d...." % ((offset+1), end_cnt), end="")
            start_tm = datetime.now()
            ents = self.get_entities(GET_LIMIT, offset)
            end_tm = datetime.now()
            if (ents == None):
                if (verbose):
                    print("failed")
                return None
            if (verbose):
                fetch_tm = (end_tm - start_tm).total_seconds()
                print("done (took %4.0f ms)" % ((fetch_tm * 1000)))
            offset += len(ents)
            left   -= len(ents)
            for e in ents:
                entities.append(e)
            if (left > 0):
                time.sleep(0.2)

        return entities

    # Run a script (base64 encoded) on the given MAC
    def run_script(self, mac, b64script, deferred = False):
        payload = {
            'serialNumber': mac,
            'type': "shell",
            'script': b64script.decode("ascii"),
            'when': 0,
            'deferred': deferred
        }
        uri = "/api/v1/device/%s/script" % mac
        resp = self.api_call("owgw", "POST", uri, payload)
        if ('results' not in resp or 'status' not in resp['results']):
            return None
        return resp['results']['status']

    # Initiate a FW update */
    def update_fw(self, mac, fw_url, keep_redirector = True):
        payload = {
            'serialNumber': mac,
            'uri': fw_url,
            'when': 0,
            'keepRedirector': keep_redirector
        }
        uri = "/api/v1/device/%s/upgrade" % mac
        resp = self.api_call("owgw", "POST", uri, payload)
        if ('ErrorCode' in resp):
            status = { 'resultCode': resp['ErrorCode'], 'text': resp['ErrorDescription'] }
            return status
        if ('results' not in resp or 'status' not in resp['results']):
            return None
        status = resp['results']['status']
        status['UUID'] = resp['UUID']
        return status

    def cmd_status(self, mac, cmd_uuid):
        uri = "/api/v1/command/%s?serialNumber=%s" % (cmd_uuid, mac)
        return self.api_call("owgw", "GET", uri)

    def load_cache(self, name):
        cfn = "cache/%s-%s.json" % (self.deployment, name)
        if (not os.path.exists(cfn)):
            return None

        mts = os.path.getmtime(cfn)
        last_modified = datetime.fromtimestamp(mts)
        if ((datetime.now() - last_modified) > timedelta(seconds=CACHE_TIME)):
            return None

        f = open(cfn)
        cache_data = json.load(f)
        f.close()
        return cache_data

    def save_cache(self, name, data):
        cfn = "cache/%s-%s.json" % (self.deployment, name)
        if (not os.path.isdir("cache")):
            os.mkdir("cache")
        with open(cfn, "w") as outfile:
            json.dump(data, outfile)

    def matching_targets(self, devices, pdata, org = None, venue = None, connected_only = True):
        targets = []
        for x in devices:
            if (connected_only and not x['connected']):
                continue
            dmac = x['serialNumber']
            inv = pdata.get_inventory_by_mac(dmac)
            if (inv == None):
                continue
            dname = inv['name']
            dmodel = inv['deviceType']
            if ('venue' in inv):
                ext = inv['venue']
            else:
                ext = x['venue']
            v = pdata.get_venue_by_uuid(ext)
            if (v == None and venue):
                continue
            if (not v):
                # Can't look up org from here, so skip
                continue
            vname = v['name']
            if (venue):
                if (vname != venue):
                    continue
            e = pdata.get_entity_by_uuid(v['entity'])
            if (e == None and org):
                continue
            if (e):
                ename = e['name']
            else:
                ename = 'unknown'
            if (org):
                if (ename != org):
                    continue

            target = {
                'mac': dmac,
                'name': dname,
                'model': dmodel,
                'org': ename,
                'venue': vname
            }
            targets.append(target)

        return targets

#==================================================================================================================

class ProvData:
    # Init CloudSDK Provisioning Data class
    def __init__(self, cloudsdk_api, verbose = True, limit = None, no_cache = None):
        if (cloudsdk_api == None):
            raise Exception("[cloudsdk] error: ProvData requires cloudsdk.API handle passed in")
        if (verbose):
            print("[cloudsdk] Loading %s provisioning data" % cloudsdk_api.deployment)

        # Check if we can use cache
        if (not no_cache):
            prov_data = cloudsdk_api.load_cache("ProvData")
            if (prov_data):
                self.inventory = prov_data['inventory']
                self.venues    = prov_data['venues']
                self.entities  = prov_data['entities']
                if (verbose):
                    print("[cloudsdk]    -> Loaded from cache: %d inv, %d venues, %d entities" %
                                                          (len(self.inventory), len(self.venues), len(self.entities)))
                return

        # Load fresh info
        self.inventory = cloudsdk_api.load_all_inventory(verbose=verbose, limit=limit)
        self.venues    = cloudsdk_api.load_all_venues(verbose=verbose, limit=limit)
        self.entities  = cloudsdk_api.load_all_entities(verbose=verbose, limit=limit)

        # Store in cache
        prov_data = { 'inventory': self.inventory, 'venues': self.venues, 'entities': self.entities }
        cloudsdk_api.save_cache("ProvData", prov_data)
        return

    # Get inventory entry by device MAC (serial number)
    def get_inventory_by_mac(self, mac):
        for inv in self.inventory:
            if ('serialNumber' in inv and inv['serialNumber'] == mac):
                return inv
        return None

    # Get inventory entry by uuid
    def get_inventory_by_uuid(self, uuid):
        for inv in self.inventory:
            if ('id' in inv and inv['id'] == uuid):
                return inv
        return None

    # Get venue by name (and optionally entity)
    def get_venue_by_name(self, name, entity_uuid = None):
        for venue in self.venues:
            if ('name' in venue and venue['name'] == name):
                if (entity_uuid and 'entity' in venue and venue['entity'] != entity_uuid):
                    continue
                return venue
        return None

    # Get venue by uuid
    def get_venue_by_uuid(self, uuid):
        for venue in self.venues:
            if ('id' in venue and venue['id'] == uuid):
                return venue
        return None

    # Get entity by name
    def get_entity_by_name(self, name, entity_uuid = None):
        for entity in self.entities:
            if ('name' in entity and entity['name'] == name):
                return entity
        return None

    # Get entity by uuid
    def get_entity_by_uuid(self, uuid):
        for entity in self.entities:
            if ('id' in entity and entity['id'] == uuid):
                return entity
        return None

    # Get device info (name, entity, venue)
    def get_device_info(self, mac, mark_unknown = False):
        if (mark_unknown):
            fail_ret = { 'mac': mac, 'name': 'unknown', 'entity': 'unknown', 'venue': 'unknown' }
        else:
            fail_ret = None
        inv = self.get_inventory_by_mac(mac)
        if (inv == None):
            return fail_ret
        venue = self.get_venue_by_uuid(inv['venue'])
        if (venue == None):
            return fail_ret
        entity = self.get_entity_by_uuid(venue['entity'])
        if (entity == None):
            return fail_ret

        return { 'mac': mac, 'name': inv['name'], 'entity': entity['name'], 'venue': venue['name'] }

