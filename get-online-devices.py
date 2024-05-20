#!/usr/bin/python3

import sys
import os
import time
import json
import csv
import argparse
from datetime import datetime

sys.path.append('modules/')
sys.path.append('config/')

from modules import cloudsdk

STATE_THRESHOLDS = [ 3000, 200000 ]
RRM_STATES = [ "INVALID", "CAN_STEER", "STEERING", "BACKOFF", "DISABLED", "MAX_REACHED" ]
MEM_THRESHOLD = 80

def loadStats(capi, mac):
    global _state_count, _state_min, _state_min_mac, _state_max, _state_max_mac, _state_avg, _state_warning
    global STATE_THRESHOLDS

    # Get Latest Single Device Stats
    print("   -> Loading latest stats for " + mac, end = ": ")
    start_tm = datetime.now()
    retries = 3
    try_no = 1
    while(try_no <= retries):
        try:
            stats = capi.get_device_stats(mac)
        except Exception as e:
            print("Retrying...", end = "")
            time.sleep(0.2)
        else:
            break
        try_no = try_no + 1
    if (try_no > retries):
        print("Failed")
        exit(1)
    end_tm = datetime.now()
    fetch_tm = (end_tm - start_tm).total_seconds()

    dsfn = "%s-last-device-stats-%s.json" % (capi.deployment, end_tm.strftime("%Y%m%d-%H%M%S"))
    with open(dsfn, "w") as outfile:
        json.dump(stats, outfile, indent=2)
    fs = os.stat(dsfn)
    if (fs):
        if (_state_avg == 0):
            _state_avg = fs.st_size
        else:
            _state_avg = ((_state_avg * _state_count) + fs.st_size) / (_state_count + 1)
        _state_count += 1
        if (_state_min == 0 or fs.st_size < _state_min):
            _state_min = fs.st_size
            _state_min_mac = mac
        if (_state_max == 0 or fs.st_size > _state_max):
            _state_max = fs.st_size
            _state_max_mac = mac
        print("%6d bytes (took %4.0f ms)" % (fs.st_size, (fetch_tm * 1000)));
        if (fs.st_size < STATE_THRESHOLDS[0] or fs.st_size > STATE_THRESHOLDS[1]):
            sw = { 'mac': mac, 'size': fs.st_size }
            _state_warning.append(sw)
    os.remove(dsfn)
    return stats

def processSurvey(nd, band, survey):
    global survey_data;

    if (len(survey) == 0):
        return

    for s in survey:
        ns = { }

        # Workaround APs giving out old/wrong format
        if 'agg_15m' not in s:
            continue

        # copy data from nd
        for x in ['mac', 'name', 'venue', 'org', 'model', 'firmware']:
            ns[x] = nd[x]

        ns['band'] = band

        # copy data from survey
        if 'on-chan' in s:
            ns['on-chan'] = s['on-chan']
        else:
            ns['on-chan'] = 'unknown'
        for x in ['channel', 'noise_floor', 'active_ms', 'busy_ms', 'busy_self_ms', 'busy_tx_ms', 'last_on_chan_secs_go', 'rrm_airtime_pct']:
            if x in s:
                ns[x] = s[x]
            else:
                ns[x] = -1

        # copy 15m agg data
        for x in ['active_ms', 'busy_ms', 'busy_self_ms', 'busy_tx_ms', 'num_samples']:
            if x in s['agg_15m']:
                k = 'agg_15m_' + x
                ns[k] = s['agg_15m'][x]
            else:
                ns[k] = -1

        survey_data.append(ns)

    return

def processNeighbors(nd, band, neighbors):
    global neighbors_data

    if (len(neighbors) == 0 or len(neighbors.keys()) == 0):
        return

    for ssid in neighbors.keys():
        nl = neighbors[ssid]
        for n in nl:
            nn = { }

            # copy data from nd
            for x in ['mac', 'name', 'venue', 'org', 'model', 'firmware']:
                nn[x] = nd[x]

            nn['band'] = band
            nn['ssid'] = ssid

            # copy data from neighbor
            if 'bssid' in n:
                nn['bssid'] = n['bssid']
            else:
                nn['bssid'] = 'unknown'
            if 'in_network' in n:
                nn['in_network'] = n['in_network']
            else:
                nn['in_network'] = False
            for x in ['channel', 'rssi', 'last_seen_secs_ago']:
                if x in n:
                    nn[x] = n[x]
                else:
                    nn[x] = -1

            neighbors_data.append(nn)

    return

def newAPClient(nd, intf = None, ssid = None, assoc = None):
    if (intf and ssid and assoc):
        apc = {
                'connected': True,
                'band': ssid['band'],
                'ssid': ssid['ssid'],
                'connected_time': assoc['connected'],
                'rssi': assoc['rssi'],
                'avg_ack_rssi': assoc['ack_signal_avg'],
                'rx_packets': assoc['rx_packets'],
                'rx_bytes': assoc['rx_bytes'],
                'tx_packets': assoc['tx_packets'],
                'tx_bytes': assoc['tx_bytes']
        }
        if 'rx_rate' in assoc and 'bitrate' in assoc['rx_rate']:
            apc['rx_rate'] = assoc['rx_rate']['bitrate'] / 1000
        else:
            apc['rx_rate'] = 0
        if 'tx_rate' in assoc and 'bitrate' in assoc['tx_rate']:
            apc['tx_rate'] = assoc['tx_rate']['bitrate'] / 1000
        else:
            apc['tx_rate'] = 0
        if 'dynamic_vlan' in assoc:
            apc['vlan_id'] = "D-%d" % assoc['dynamic_vlan']
        elif 'vlan_id' in intf:
            apc['vlan_id'] = "S-%d" % intf['vlan_id']
        else:
            apc['vlan_id'] = ""
    else:
        apc = {
                'connected': False,
                'band': "",
                'ssid': "",
                'connected_time': 0,
                'rssi': 0,
                'avg_ack_rssi': 0,
                'rx_packets': 0,
                'rx_bytes': 0,
                'tx_packets': 0,
                'tx_bytes': 0,
                'rx_rate': 0,
                'tx_rate': 0,
                'vlan_id': ""
        }

    # Store a pointer to the device
    apc['_device'] = nd

    apc['rrm_state'] = "N/A"
    apc['rrm_bands'] = 0
    apc['rrm_active'] = False
    apc['rrm_pps'] = 0
    for st in ['upsteer', 'sticky', 'downsteer']:
        for kt in ['btm', 'legacy']:
            for sn in ['total', 'success', 'fail']:
                en = "rrm_%s_%s_%s" % (st, kt, sn)
                apc[en] = 0
    apc['rrm_cap_wnm'] = False
    apc['rrm_cap_active'] = False
    apc['rrm_cap_passive'] = False
    apc['rrm_cap_table'] = False
    apc['rrm_cap_link'] = False
    apc['rrm_cap_stats'] = False

    return apc

def processAssocClients(nd, ssid, intf):
    global clients_by_ap

    if not 'associations' in ssid:
        return

    amac = nd['mac']
    for assoc in ssid['associations']:
        cmac = assoc['station']
        apc = newAPClient(nd, intf, ssid, assoc)

        if cmac in clients_by_ap:
            if amac in clients_by_ap[cmac]['ap']:
                clients_by_ap[cmac]['dup'] = clients_by_ap[cmac]['dup'] + 1
                if (apc['connected_time'] > clients_by_ap[cmac]['ap'][amac]['connected_time']):
                    # This is older entry, ignore it
                    continue
                # ...fall through: newer entry, replace it
            clients_by_ap[cmac]['ap'][amac] = apc
        else:
            clients_by_ap[cmac] = { 'dup': 0, 'ap': { amac: apc } }

def processRRMInfo(nd, rrminfo):
    global RRM_STATES
    global clients_by_ap

    amac = nd['mac']
    for ric in rrminfo:
        cmac = ric['mac']

        if cmac in clients_by_ap and amac in clients_by_ap[cmac]['ap']:
            apc = clients_by_ap[cmac]['ap'][amac]
        else:
            apc = newAPClient(nd)

        if ric['state'] is None:
            continue
        if ric['state'] >= 1 and ric['state'] < len(RRM_STATES):
            apc['rrm_state'] = RRM_STATES[ric['state']]
        else:
            apc['rrm_state'] = str(ric['state'])
        apc['rrm_bands'] = ric['supported_bands']
        apc['rrm_active'] = ric['active']
        apc['rrm_pps'] = ric['pps_rx']
        for st in ['upsteer', 'sticky', 'downsteer']:
            for kt in ['btm', 'legacy']:
                for sn in ['total', 'success', 'fail']:
                    en = "rrm_%s_%s_%s" % (st, kt, sn)
                    apc[en] = ric['stats'][st][kt][sn]
        apc['rrm_cap_wnm'] = ric['wnm']
        apc['rrm_cap_active'] = ric['rrm']['beacon_active_measure']
        apc['rrm_cap_passive'] = ric['rrm']['beacon_passive_measure']
        apc['rrm_cap_table'] = ric['rrm']['beacon_table_measure']
        apc['rrm_cap_link'] = ric['rrm']['link_measure']
        apc['rrm_cap_stats'] = ric['rrm']['statistics_measure']

        if (cmac in clients_by_ap):
            clients_by_ap[cmac]['ap'][amac] = apc
        else:
            clients_by_ap[cmac] = { 'dup': 0, 'ap': { amac: apc } }

def findDupLAN(interfaces, ifname, name):
    for intf in interfaces:
        if (intf['name'] == ifname):
            continue
        for eth in intf['ethernet']:
            if not 'select-ports' in eth:
                continue
            for pn in eth['select-ports']:
                if name == "LAN*" and pn.startswith('LAN'):
                    return True
                if pn == name:
                    return True
    return False

# Parse command line arguments
parser = argparse.ArgumentParser(description="Online Device Statistics")
parser.add_argument('-d', '--deployment', required=True, action='store', help="Set deployment")
parser.add_argument('-O', '--outdir', action='store', help='Set output dir (default is results/<deployment>)')
parser.add_argument('-e', '--expand', action='store_true', help="Print expanded info where possible")
parser.add_argument('-o', '--org', action='store', help="Filter by org name")
parser.add_argument('-v', '--venue', action='store', help="Filter by venue name")
args = parser.parse_args()

# Initialize the CloudSDK API
capi  = cloudsdk.API(deployment=args.deployment)

if (args.outdir):
    prefix = args.outdir
else:
    if (not os.path.isdir("results")):
        os.mkdir("results")
    prefix = "results/%s" % (capi.deployment)

if (not os.path.isdir(prefix)):
    os.mkdir(prefix)

# Load the provisioning data
pdata = cloudsdk.ProvData(capi, no_cache = True)
now = datetime.now()

# Get all devices
devices = capi.load_all_devices(no_cache = True)
dev_count = len(devices)

# Get device connection statistics
cstats = capi.get_conn_stats()

print("\nThere are %d connected devices out of %d total (%d avg conn time)" % (cstats['connectedDevices'], dev_count, cstats['averageConnectionTime']))

if (args.org or args.venue):
    fstr = " (Filter: %s => %s)" % (args.org, args.venue)
else:
    fstr = ""
print("-> Processing online devices" + fstr)
online_devices = [];
survey_data = [];
neighbors_data = [];
stale_devices = [];
broken_lan_devices = [];
remote_logging_devices = [];
high_mem_devices = [];
clients_by_ap = {};
_state_count = 0
_state_min = 0
_state_min_mac = ""
_state_max = 0
_state_max_mac = ""
_state_avg = 0
_state_warning = []
cnt_total = 0
cnt_online = 0
for x in devices:
    cnt_total = cnt_total + 1
    if x['connected']:
        nd = { "mac": x['serialNumber'] }
        inv = pdata.get_inventory_by_mac(x['serialNumber'])
        if (inv == None):
            nd['name'] = "unknown"
            if (len(x['manufacturer']) > 0):
                nd['model'] = x['compatible']
            else:
                nd['model'] = "unknown"
        else:
            nd['name'] = inv['name']
            nd['model'] = inv['deviceType']
        if (inv != None and 'venue' in inv):
            ext = inv['venue']
        else:
            ext = x['venue']
        v = pdata.get_venue_by_uuid(ext)
        if (v == None):
            nd['venue'] = "unknown"
            nd['org'] = "unknown"
        else:
            nd['venue'] = v['name']
            e = pdata.get_entity_by_uuid(v['entity'])
            if (e == None):
                nd['org'] = "unknown"
            else:
                nd['org'] = e['name']

        if (args.org):
            if (nd['org'].lower() != args.org.lower()):
                continue
        if (args.venue):
            if (nd['venue'].lower() != args.venue.lower()):
                continue
        cnt_online = cnt_online + 1

        nd['num_assocs'] = x['associations_2G'] + x['associations_5G'] + x['associations_6G']
        idx = x['firmware'].find("Shasta")
        if (idx < 0):
            if (len(x['firmware']) == 0):
                nd['firmware'] = "unknown"
            else:
                nd['firmware'] = x['firmware']
        else:
            nd['firmware'] = x['firmware'][idx:]

        nd['conf_2g'] = "unknown"
        nd['conf_2g_bw'] = "unknown"
        nd['conf_5g'] = "unknown"
        nd['conf_5g_bw'] = "unknown"
        nd['conf_6g'] = "unknown"
        nd['conf_6g_bw'] = "unknown"
        if 'configuration' in x and 'radios' in x['configuration']:
            for r in x['configuration']['radios']:
                if r['band'] == '2G':
                    nd['conf_2g'] = str(r['channel'])
                    nd['conf_2g_bw'] = str(r['channel-width'])
                elif r['band'] == '5G':
                    nd['conf_5g'] = str(r['channel'])
                    nd['conf_5g_bw'] = str(r['channel-width'])
                elif r['band'] == '6G':
                    nd['conf_6g'] = str(r['channel'])
                    nd['conf_6g_bw'] = str(r['channel-width'])
            dup_cnt = 0
            for intf in x['configuration']['interfaces']:
                if not 'ethernet' in intf:
                    continue
                for eth in intf['ethernet']:
                    if not 'select-ports' in eth:
                        continue
                    for pn in eth['select-ports']:
                        if pn.startswith('LAN'):
                            if findDupLAN(x['configuration']['interfaces'], intf['name'], pn):
                                dup_cnt += 1
            if (dup_cnt > 0):
                bl = { 'mac': nd['mac'], 'dup_cnt': dup_cnt }
                broken_lan_devices.append(bl)

        if 'configuration' in x and 'services' in x['configuration']:
            services_conf = x['configuration']['services']
            if 'log' in services_conf and 'host' in services_conf['log']:
                rl = { 'mac': nd['mac'], 'host': services_conf['log']['host'], 'port': services_conf['log']['port'] }
                remote_logging_devices.append(rl)

        stats = loadStats(capi, nd['mac'])
        time.sleep(0.2) # so we don't slam the API

        if 'unit' in stats:
            ap_time = datetime.fromtimestamp(stats['unit']['localtime'])
            nd['last_state'] = (now - ap_time).total_seconds()
            if (nd['last_state'] > 120):
                sd = { 'mac': nd['mac'], 'last_state': nd['last_state'] }
                stale_devices.append(sd)
            nd['uptime'] = stats['unit']['uptime']
            nd['up_days'] = round(nd['uptime'] / 86400, 2)
            if 'cpu_load' in stats['unit']:
                nd['cpu_busy_pct'] = stats['unit']['cpu_load'][0]
            else:
                nd['cpu_busy_pct'] = -1
            nd['cpu_load_1m'] = stats['unit']['load'][0]
            nd['cpu_load_5m'] = stats['unit']['load'][1]
            nd['cpu_load_15m'] = stats['unit']['load'][2]

            mem_free = stats['unit']['memory']['free']
            mem_total = stats['unit']['memory']['total']
            mem_used = mem_total - mem_free
            nd['mem_used_pct'] = round((mem_used * 100 / mem_total), 2)
            nd['mem_free_pct'] = round((mem_free * 100 / mem_total), 2)
            if (nd['mem_used_pct'] > MEM_THRESHOLD):
                md = { 'mac': nd['mac'], 'mem_used_pct': nd['mem_used_pct'] }
                high_mem_devices.append(md)
        else:
            nd['last_state'] = -1
            nd['uptime'] = -1
            nd['up_days'] = -1
            nd['cpu_busy_pct'] = -1
            nd['cpu_load_1m'] = -1
            nd['cpu_load_5m'] = -1
            nd['cpu_load_15m'] = -1
            nd['mem_used_pct'] = -1
            nd['mem_free_pct'] = -1

        nd['num_ssids'] = 0
        if 'interfaces' in stats:
            nd['num_ifaces'] = len(stats['interfaces'])
            for x in stats['interfaces']:
                if 'ssids' in x:
                    nd['num_ssids'] = nd['num_ssids'] + len(x['ssids'])
                    for ssid in x['ssids']:
                        processAssocClients(nd, ssid, x)
        else:
            nd['num_ifaces'] = 0

        for x in ['2g', '5g', '6g']:
            nd["chan_" + x] = 0
            nd["width_" + x] = 0

        if 'radios' in stats:
            for r in stats['radios']:
                if r['band'][0] == "2G":
                    x = '2g'
                elif r['band'][0] == "5G":
                    x = '5g'
                elif r['band'][0] == "6G":
                    x = '6g'
                else:
                    continue
                nd["chan_" + x] = r['channel']
                nd["width_" + x] = r['channel_width']

                if 'survey' in r:
                    processSurvey(nd, x, r['survey']);
                if 'neighbors' in r:
                    processNeighbors(nd, x, r['neighbors']);

        if 'rrm-info' in stats:
            processRRMInfo(nd, stats['rrm-info'])

        nd['wan_carrier'] = -1
        nd['wan_speed'] = -1
        nd['wan_duplex'] = -1
        if 'link-state' in stats:
            if 'upstream' in stats['link-state']:
                if 'WAN' in stats['link-state']['upstream']:
                    nd['wan_carrier'] = stats['link-state']['upstream']['WAN']['carrier']
                    nd['wan_speed'] = stats['link-state']['upstream']['WAN']['speed']
                    nd['wan_duplex'] = stats['link-state']['upstream']['WAN']['duplex']

        online_devices.append(nd)

print("\nThere are %d total clients across the %d connected devices" % (len(clients_by_ap), cstats['connectedDevices']))
print("-> Processing client stats and RRM info")
clients_by_ap_data = []
clients_data = []
clients_connected = 0
for cmac in clients_by_ap.keys():
    cent = None
    cap = None
    for amac, apc in clients_by_ap[cmac]['ap'].items():
        if apc['connected']:
            if (not cent or apc['connected_time'] < cent['connected_time']):
                cent = apc.copy()
                cap = amac
        napc = apc.copy()
        del napc['_device']
        di = apc['_device']
        napc['mac'] = cmac
        napc['org'] = di['org']
        napc['venue'] = di['venue']
        napc['ap_mac'] = amac
        napc['ap_name'] = di['name']
        napc['ap_model'] = di['model']
        napc['ap_fw'] = di['firmware']
        clients_by_ap_data.append(napc)

    if cent:
        cent['mac'] = cmac
        di = cent['_device']
        cent['org'] = di['org']
        cent['venue'] = di['venue']
        del cent['_device']
        cent['ap_cnt'] = 1
        cent['dups'] = clients_by_ap[cmac]['dup']
    for amac, apc in clients_by_ap[cmac]['ap'].items():
        if not cent:
            cent = apc.copy()
            cent['mac'] = cmac
            di = cent['_device']
            cent['org'] = di['org']
            cent['venue'] = di['venue']
            del cent['_device']
            cent['ap_cnt'] = 1
            cent['dups'] = clients_by_ap[cmac]['dup']
        elif amac == cap:
            continue
        for st in ['upsteer', 'sticky', 'downsteer']:
            for kt in ['btm', 'legacy']:
                for sn in ['total', 'success', 'fail']:
                    en = "rrm_%s_%s_%s" % (st, kt, sn)
                    cent[en] = cent[en] + apc[en]
                    cent['ap_cnt'] = cent['ap_cnt'] + 1
    if cent['connected']:
        clients_connected = clients_connected + 1
    clients_data.append(cent)
print("   -> %d of them are currently connected" % clients_connected)

prefix = prefix + "/%s-%s" % (capi.deployment, now.strftime("%Y%m%d-%H%M%S"))
print("\n[" + prefix + "] Processed " + str(cnt_online) + " online devices out of " + str(cnt_total) + " total")

# Write out JSON
fn = prefix + "-online-devices.json"
print("   -> Writing JSON of online devices to " + fn)
with open(fn, "w") as outfile:
    json.dump(online_devices, outfile, indent=2)

# Write out CSV
fn = prefix + "-online-devices.csv"
print("   -> Writing CSV of online devices to " + fn)
csv_fields = ['mac', 'name', 'org', 'venue', 'model', 'firmware', 'uptime', 'up_days',
              'cpu_busy_pct', 'cpu_load_1m', 'cpu_load_5m', 'cpu_load_15m',
              'mem_used_pct', 'mem_free_pct', 'num_ifaces', 'num_ssids', 'num_assocs',
              'chan_2g', 'width_2g', 'chan_5g', 'width_5g', 'chan_6g', 'width_6g',
              'conf_2g', 'conf_5g', 'conf_6g', 'conf_2g_bw', 'conf_5g_bw', 'conf_6g_bw',
              'last_state', 'wan_carrier', 'wan_speed', 'wan_duplex']
with open(fn, "w") as outfile:
    writer = csv.DictWriter(outfile, fieldnames=csv_fields)
    writer.writeheader()
    for od in online_devices:
        writer.writerow(od)

# Survey: Write out JSON
fn = prefix + "-survey-data.json"
print("   -> Writing JSON of survey data to " + fn)
with open(fn, "w") as outfile:
    json.dump(survey_data, outfile, indent=2)

# Survey: Write out CSV
fn = prefix + "-survey-data.csv"
print("   -> Writing CSV of survey data to " + fn)
csv_fields = ['mac', 'name', 'org', 'venue', 'model', 'firmware', 'band', 'on-chan',
              'channel', 'noise_floor', 'active_ms', 'busy_ms', 'busy_self_ms',
              'busy_tx_ms', 'last_on_chan_secs_go', 'rrm_airtime_pct',
              'agg_15m_active_ms', 'agg_15m_busy_ms', 'agg_15m_busy_self_ms',
              'agg_15m_busy_tx_ms', 'agg_15m_num_samples']
with open(fn, "w") as outfile:
    writer = csv.DictWriter(outfile, fieldnames=csv_fields)
    writer.writeheader()
    for sd in survey_data:
        writer.writerow(sd)

# Neighbor: Write out JSON
fn = prefix + "-neighbors-data.json"
print("   -> Writing JSON of neighbors data to " + fn)
with open(fn, "w") as outfile:
    json.dump(neighbors_data, outfile, indent=2)

# Neighbor: Write out CSV
fn = prefix + "-neighbors-data.csv"
print("   -> Writing CSV of neighbors data to " + fn)
csv_fields = ['mac', 'name', 'org', 'venue', 'model', 'firmware', 'band', 'ssid',
              'bssid', 'in_network', 'channel', 'rssi', 'last_seen_secs_ago']
with open(fn, "w") as outfile:
    writer = csv.DictWriter(outfile, fieldnames=csv_fields)
    writer.writeheader()
    for nd in neighbors_data:
        writer.writerow(nd)

# Clients by AP: Write out JSON
fn = prefix + "-clients-by-ap.json"
print("   -> Writing JSON of Clients by AP to " + fn)
with open(fn, "w") as outfile:
    json.dump(clients_by_ap_data, outfile, indent=2)

# Clients by AP: Write out CSV
fn = prefix + "-clients-by-ap.csv"
print("   -> Writing CSV of Clients by AP to " + fn)
csv_fields = ['mac', 'org', 'venue', 'ap_mac', 'ap_name', 'ap_model', 'ap_fw', 'connected', 'band', 'ssid',
              'connected_time', 'rssi', 'avg_ack_rssi', 'rx_rate', 'tx_rate', 'rx_packets', 'rx_bytes',
              'tx_packets', 'tx_bytes', 'vlan_id', 'rrm_state', 'rrm_bands', 'rrm_active', 'rrm_pps']
for st in ['upsteer', 'sticky', 'downsteer']:
    for kt in ['btm', 'legacy']:
        for sn in ['total', 'success', 'fail']:
            en = "rrm_%s_%s_%s" % (st, kt, sn)
            csv_fields.append(en)
for x in ['wnm', 'active', 'passive', 'table', 'link', 'stats']:
    en = "rrm_cap_%s" % x
    csv_fields.append(en)
with open(fn, "w") as outfile:
    writer = csv.DictWriter(outfile, fieldnames=csv_fields)
    writer.writeheader()
    for cd in clients_by_ap_data:
        writer.writerow(cd)

# Clients: Write out JSON
fn = prefix + "-clients.json"
print("   -> Writing JSON of Clients to " + fn)
with open(fn, "w") as outfile:
    json.dump(clients_data, outfile, indent=2)

# Clients: Write out CSV
fn = prefix + "-clients.csv"
print("   -> Writing CSV of Clients to " + fn)
csv_fields = ['mac', 'org', 'venue', 'ap_cnt', 'dups', 'connected', 'band', 'ssid', 'connected_time',
              'rssi', 'avg_ack_rssi', 'rx_rate', 'tx_rate', 'rx_packets', 'rx_bytes', 'tx_packets',
              'tx_bytes', 'vlan_id', 'rrm_state', 'rrm_bands', 'rrm_active', 'rrm_pps']
for st in ['upsteer', 'sticky', 'downsteer']:
    for kt in ['btm', 'legacy']:
        for sn in ['total', 'success', 'fail']:
            en = "rrm_%s_%s_%s" % (st, kt, sn)
            csv_fields.append(en)
for x in ['wnm', 'active', 'passive', 'table', 'link', 'stats']:
    en = "rrm_cap_%s" % x
    csv_fields.append(en)
with open(fn, "w") as outfile:
    writer = csv.DictWriter(outfile, fieldnames=csv_fields)
    writer.writeheader()
    for cd in clients_data:
        writer.writerow(cd)

print("\nInformation, warnings, and errors detected:")
print("   -> State Size Info:")
dinfo = pdata.get_device_info(_state_min_mac, mark_unknown=True)
print("        Min: %6d bytes (MAC: %s, %s => %s => %s)"
                            % (round(_state_min), _state_min_mac, dinfo['entity'], dinfo['venue'], dinfo['name']))
dinfo = pdata.get_device_info(_state_max_mac, mark_unknown=True)
print("        Max: %6d bytes (MAC: %s, %s => %s => %s)"
                            % (round(_state_max), _state_max_mac, dinfo['entity'], dinfo['venue'], dinfo['name']))
print("        Avg: %6d bytes" % (round(_state_avg)))

if (len(_state_warning)):
    print("   -> WARNING: Found " + str(len(_state_warning)) + " devices with state size outside of warning thresholds:")
    for sw in _state_warning:
        dinfo = pdata.get_device_info(sw['mac'], mark_unknown=True)
        print("       -> %s state size is %6d bytes (%s => %s => %s)"
                            % (sw['mac'], round(sw['size']), dinfo['entity'], dinfo['venue'], dinfo['name']))

if (len(high_mem_devices)):
    print("   -> WARNING: Found " + str(len(high_mem_devices)) + " devices with memory > " + str(MEM_THRESHOLD) + "%:")
    for md in high_mem_devices:
        dinfo = pdata.get_device_info(md['mac'], mark_unknown=True)
        print("       -> %s mem usage is %d%% (%s => %s => %s)"
                            % (md['mac'], md['mem_used_pct'], dinfo['entity'], dinfo['venue'], dinfo['name']))

if (len(stale_devices)):
    print("   -> WARNING: Found " + str(len(stale_devices)) + " devices with stale stats:")
    for sd in stale_devices:
        dinfo = pdata.get_device_info(sd['mac'], mark_unknown=True)
        print("       -> %s last updated %d seconds ago (%s => %s => %s)"
                            % (sd['mac'], sd['last_state'], dinfo['entity'], dinfo['venue'], dinfo['name']))

if (len(remote_logging_devices)):
    print("   -> WARNING: There are %d devices remote logging" % len(remote_logging_devices))
    if args.expand:
        for rl in remote_logging_devices:
            dinfo = pdata.get_device_info(rl['mac'], mark_unknown=True)
            print("       -> %s logging to %s:%d (%s => %s => %s)"
                            % (rl['mac'], rl['host'], rl['port'], dinfo['entity'], dinfo['venue'], dinfo['name']))

if (len(broken_lan_devices)):
    print("   -> ERROR: Found " + str(len(broken_lan_devices)) + " devices with broken LAN config:")
    for bl in broken_lan_devices:
        dinfo = pdata.get_device_info(bl['mac'], mark_unknown=True)
        print("       -> %s has LAN duplicated %d times (%s => %s => %s)"
                            % (bl['mac'], bl['dup_cnt'], dinfo['entity'], dinfo['venue'], dinfo['name']))
