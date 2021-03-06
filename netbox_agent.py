#!/usr/bin/python3
# requirement: requests, netifaces, netaddr, pyroute2

import configparser
import logging
import os
import re
import socket
import urllib
import platform

import requests
import dmidecode
import netifaces
import netaddr

if platform.system() == 'Linux':
    import pyroute2, ethtool

def get_phy_int(interface):        
        ip = pyroute2.IPRoute()
        if len(ip.link_lookup(ifname=interface)) == 0 :
            return None
        link = ip.link("get", index=ip.link_lookup(ifname=interface)[0])[0]        
        if link.get_attr('IFLA_LINK_NETNSID') != None:
            return None
        elif link.get_attr('IFLA_LINKINFO') != None and get_link_type(link) != 'vlan':
            return None
        raw_link_id = list(filter(lambda x:x[0]=='IFLA_LINK', link['attrs']))
        if len(raw_link_id) == 1:            
            raw_index = raw_link_id[0][1]
            try:
                raw_link = ip.link("get", index=raw_index)[0]
                phy_int=list(filter(lambda x:x[0]=='IFLA_IFNAME', raw_link['attrs']))[0][1]
                return phy_int
            except pyroute2.netlink.exceptions.NetlinkError:
                return interface
        else:
            return interface

def convert_v6_to_simple(addr, ifname):
    address = addr['addr'].replace('%{}'.format(ifname), '')
    netmask = addr['netmask'].split('/')[-1]

    return address, netmask

def get_vid(vlan_if):
    ip = pyroute2.IPRoute()
    link = ip.get_links(ip.link_lookup(ifname=vlan_if)[0])[0]
    vid = link.get_attr('IFLA_LINKINFO').get_attr('IFLA_INFO_DATA').get_attr(
        'IFLA_VLAN_ID')
    return vid

def get_link_type(link):
    return link.get_attr('IFLA_LINKINFO').get_attr('IFLA_INFO_KIND')    

class NetBoxAgent():    
    def __init__(self, configFile):

        if not os.path.exists(configFile):
            self.create_conf(configFile)

        config, optional_conf = self.load_conf(configFile)
        self.create_header(config['DEFAULT']['Token'])
        self.get_site(config['DEFAULT']['sitename'])

        if 'rack_group' in optional_conf: 
            self.get_rack_group(optional_conf['rack_group'])
        self.get_rack(config['DEFAULT']['rack_name'])
        if 'position' in optional_conf:
            self.rack_position = optional_conf['position']
            self.rack_face = int(optional_conf['face'])
        else: self.rack_position = None

        if 'manufacturer' in optional_conf:
            self.manufacturer_name = optional_conf['manufacturer']
            self.model_name = optional_conf['model_name']
        else : self.manufacturer_name = None

        if 'height' in optional_conf:
            self.height = optional_conf['height']
        
        if 'device_role_color' in config['DEFAULT']:
            self.get_device(config['DEFAULT']['device_role'], 
            config['DEFAULT']['device_role_color'])
        else:
            self.get_device(config['DEFAULT']['device_role'])
        
    
    def create_header(self, token):        
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': 'Token ' + token
        }

    def create_conf(self, configFile):
        logging.debug('Creating config file {}'.format(configFile))
        config = configparser.ConfigParser()        
        addr = input('Netbox Server address (e.g. http://localhost:8080) : ')
        config['DEFAULT']['api_base_url'] = '{0}/api'.format(addr)
        config['DEFAULT']['Token'] = input('Authentication Token: ')
        config['DEFAULT']['sitename'] = input('Site name: ')
        config['Optional'] = {}
        config['Optional']['rack_group'] = input('Rack Group: ')
        config['DEFAULT']['rack_name'] = input('Rack Name: ')
        config['DEFAULT']['device_role'] = input('Device Role: ')
        config['DEFAULT']['device_role_color'] = input(
            'Device Role Color Hex (e.g. aa1409): ')
        is_mounted = input('Is the device mounted? (Y/N)')
        if is_mounted.lower() == 'y':
            config['Optional']['position'] = input(
                'Mounted rack position (lowest, from 1) : ')
            config['Optional']['face'] = input(
                'Mounted rack face (0 for front, 1 for back) : ')
        is_manuf_known = input('Do you know the manufacturer' 
            'and model name? (Y/N)')
        if is_manuf_known.lower() == 'y':
            config['Optional']['manufacturer'] = input('Manufacturer: ')
            config['Optional']['model_name'] = input('Model name: ')

        with open(configFile, 'w') as config_file:
            config.write(config_file)
            logging.debug('Configuration file written : {0}'.format(
                configFile))

    def load_conf(self, configFile):        
        if not os.path.exists(configFile): self.create_conf(configFile)            
        config = configparser.ConfigParser()
        config.read(configFile)
        self.base_url = config['DEFAULT']['api_base_url']
        self.token = 'Token {0}'.format(config['DEFAULT']['Token'])
        
        optional_conf = config['Optional']

        return config, optional_conf

    def query_get(self, obj_name, params):
        param_str = urllib.parse.urlencode(params)
        resp = requests.get('{0}/{1}/?{2}'.format(
            self.base_url, obj_name, param_str),headers=self.headers).json()

        if 'detail' in resp and resp['detail'] == 'Not found.': return None
        elif 'results' in resp and len(resp['results']) == 0 : return None
        elif 'results' in resp : return resp['results']
        elif type(resp) == dict: return resp
        else: raise Exception()


    def query_post(self, obj_name, data):
        if 'name' in data and len(data['name']) > 50:
            data['name'] = data['name'][:50]

        resp = requests.post('{0}/{1}/'.format(self.base_url, obj_name), 
        json=data, headers=self.headers, allow_redirects=False)
        
        if resp.status_code != 201: raise Exception(
            'Failed to create {0} : {1} status {2}: {3}'
            .format(obj_name, next(iter( data.items())), resp.status_code, 
            resp.reason))
        else : 
            return resp.json()

    def query_delete(self, obj_name, id):        
        resp = requests.delete('{0}/{1}/{2}/'.format(self.base_url, obj_name, 
        id), headers=self.headers, allow_redirects=False)

        if resp.status_code != 204: raise Exception(
            'Failed to delete {0} : {1} status {2}: {3}'
            .format(obj_name, id, resp.status_code, resp.reason))

    def query_patch(self, obj_name, id, data):        
        resp = requests.patch('{0}/{1}/{2}/'.format(self.base_url, obj_name, 
        id), json=data, headers=self.headers, allow_redirects=False)

        if resp.status_code != 200: raise Exception(
            'Failed to patch {0} : {1} status {2}: {3}'
            .format(obj_name, id, resp.status_code, resp.reason))
        else : 
            return resp.json() 

    def get_site(self, sitename):        
        params = {'name' : sitename}

        site = self.query_get('dcim/sites',params)
        if site == None : self.create_site(sitename)
        else: self.site = site[0]

    def create_site(self, sitename):
        logging.debug('creating site ' + sitename)
        data = {'name' : sitename, 'slug' : sitename}

        self.site = self.query_post('dcim/sites', data)
        print('test')
        
    def get_rack_group(self, rack_group_name):
        params = {'site_id' : self.site['id'], 'name' : rack_group_name}

        rack_group = self.query_get('dcim/rack-groups',params)
        if rack_group == None: self.create_rack_group(rack_group_name)
        else: self.rack_group = rack_group[0]

    def create_rack_group(self, rack_group_name):        
        logging.debug('Creating rack group ' + rack_group_name)
        data = {
            'name' : rack_group_name, 'slug' : rack_group_name, 
            'site' : self.site['id']
            }
        self.rack_group = self.query_post('dcim/rack-groups', data)        
        logging.debug('Rack group created {0}({1})'.format(
            self.rack_group['name'], self.rack_group['id']))   

    def get_rack(self, rack_name):        
        params = {'name' : rack_name, 'site_id' : self.site['id']}
        if hasattr(self, 'rack_group'):
            params['group_id'] = self.rack_group['id']
        
        rack = self.query_get('dcim/racks',params)
        if rack == None: self.create_rack(rack_name)
        else: self.rack = rack[0]
        
    # TODO: rack_role and tenent (type and width?)
    def create_rack(self, rack_name):
        logging.debug('Creating rack ' + rack_name)
        data = {
            'name' : rack_name, 'slug' : rack_name, 
            'site' : self.site['id']
        }

        if hasattr(self, 'rack_group'):
            data['group'] = self.rack_group['id']
        
        self.rack = self.query_post('dcim/racks', data)        
        logging.debug('Rack created {0}({1})'.format(self.rack['name'], 
        self.rack['id']))   

    def get_device_role(self, device_role_name, color):
        params = {'name' : device_role_name}

        device_role = self.query_get('dcim/device-roles', params)
        if device_role == None: self.create_device_role(device_role_name,
            color)
        else: self.device_role = device_role[0]
        
    def create_device_role(self, device_role_name, device_role_color):
        logging.debug('Creating device role ' + device_role_name)
        data = {'name' : device_role_name, 'slug' : device_role_name, 
        'color' : device_role_color}

        self.device_role = self.query_post('dcim/device-roles', data)
        logging.debug('Device role created {0}({1})'.format(
            self.device_role['name'], self.device_role['id']))

    def get_manufacturer(self, manufacturer):
        param = {'name' : manufacturer}

        manufacturers = self.query_get('dcim/manufacturers', param)
        if manufacturers == None : self.create_manufacturer(manufacturer)
        else : self.manufacturer = manufacturers[0]

    def create_manufacturer(self, manufacturer):
        logging.debug('Creating manufacturer ' + manufacturer)
        manufacturer_slug = re.sub(r'([^-a-zA-Z0-9_])+','_',
                manufacturer)
        if manufacturer_slug.endswith('_') : 
            manufacturer_slug = manufacturer_slug[:-1]
        data = {'name' : manufacturer, 'slug' : manufacturer_slug}
        
        self.manufacturer = self.query_post('dcim/manufacturers', data)
        logging.debug('Manufacturer created {0}({1})'.format(
            self.manufacturer['name'], self.manufacturer['id']))

    def get_device_type(self):
        sysinfo = dmidecode.profile()
        
        for item in sysinfo:
            if self.manufacturer_name == None:
                if 'system' in item[0] and ('Manufacturer' in item[1] and 
                'Product Name' in item[1]):
                    self.manufacturer_name = item[1]['Manufacturer']                
                    self.model_name = item[1]['Product Name']                
                    logging.debug('System information found {0} {1}'
                    ''.format(self.manufacturer_name, self.model_name))
            
            if 'chassis' in item[0]:
                height = item[1]['Height']
                if height == 'Unspecified':
                    if not hasattr(self, 'height'): self.height = 1                    
                else : self.height = int(height.split(' ')[0])
                logging.debug('Chassis information found. Height {0}'
                ''.format(height))
                        

        self.get_manufacturer(self.manufacturer_name)
        
        param = {'model' : self.model_name}
        device_type = self.query_get('dcim/device-types', param)
        if device_type == None: self.create_device_type(self.model_name,self.height)
        else : self.update_device_type(device_type[0])
            
    def update_device_type(self, device_type):
        if device_type['manufacturer']['id'] != self.manufacturer['id']:
            data = {'manufacturer' : self.manufacturer['id']}
            self.query_patch('dcim/device-types', device_type['id'], data)        

            param = {}
            self.device_type = self.query_get('dcim/device-types/{}'.format(
                device_type['id']), param)
        else:
            self.device_type = device_type
        
    
    def create_device_type(self, model_name, height):
        logging.debug('Creating device type ' + model_name)
        model_name_slug = re.sub(r'[^-a-zA-Z0-9_]','_',
                model_name)                
        if model_name_slug.endswith('_') : 
            model_name_slug = model_name_slug[:-1]
        data = {'manufacturer' : self.manufacturer['id'], 
        'model' : model_name, 'slug' : model_name_slug, 'u_height': height}

        self.device_type = self.query_post('dcim/device-types', data)
        logging.debug('Device  created {0}({1})'.format(
            self.device_type['model'], self.device_type['id']))

    def get_device(self, role, role_color="aa1409"):
        device_name = socket.gethostname()
        self.get_device_role(role, role_color)
        self.get_device_type()

        param = {'name' : device_name}        
        device = self.query_get('dcim/devices', param)        
        if device == None : self.create_device(device_name)
        elif len(device) > 1: raise Exception('More than 1 device found with '
            'name {}'.format(device_name))
        else : self.device = self.update_device(device[0])

    def create_device(self, device_name):
        logging.debug('Creating device ' + device_name)

        data = {'name' : device_name, 'device_type' : self.device_type['id'],
        'device_role' : self.device_role['id'], 'site' : self.site['id'], 
        'rack' : self.rack['id']}

        if self.rack_position != None:
            data['position'] = self.rack_position
            data['face'] = self.rack_face

        self.device = self.query_post('dcim/devices',data)        

    def update_device(self, prev_device):
        logging.debug('Updating Device : ' + prev_device['name'])
        data = {'name' : prev_device['name'], 'device_role' : 
        self.device_role['id'], 'site' : self.site['id'], 
        'rack' : self.rack['id'], 'device_type' : self.device_type['id']}

        if self.rack_position != None:
            data['position'] = self.rack_position
            data['face'] = self.rack_face        
        curr_device = self.query_patch('dcim/devices', prev_device['id'],data)
        
        if prev_device['device_type']['id'] != curr_device['device_type']['id']:             
            self.check_empty_device_type(prev_device['device_type']['id'])
        return curr_device

    def check_empty_device_type(self, device_type_id):
        param = {'device_type_id' : device_type_id}
        device = self.query_get('dcim/devices', param)
        if device == None:
            self.query_delete('dcim/device-types', device_type_id)

    def get_interfaces(self):
        param = {'device_id' : self.device['id']}

        return self.query_get('dcim/interfaces', param)

    def get_addresses(self, param):        
        return self.query_get('ipam/ip-addresses', param)

    def update_interfaces(self):
        logging.debug("Updating network interfaces")
        prev_ifaces = self.get_interfaces()        
        curr_ifaces = netifaces.interfaces()
        self.gateways =  netifaces.gateways()['default']
        self.prev_ifnames = []

        # Delete interfaces don't exist
        if prev_ifaces != None:
            self.prev_ifnames = [d['name'] for d in prev_ifaces]
            for prev_if in prev_ifaces:
                if prev_if['name'] not in curr_ifaces:                    
                    self.delete_interface(prev_if)

        for iface in curr_ifaces:            
            if prev_ifaces is None or iface not in self.prev_ifnames:
                self.create_interface(iface)
            elif iface in self.prev_ifnames:
                prev_iface = [d for d in prev_ifaces if d['name'] == iface][0]
                self.update_addresses(iface, prev_iface)

    def create_interface(self, ifname):
        logging.debug('Creating interface ' + ifname)
        addrs = netifaces.ifaddresses(ifname)
        
        data = {'device' : self.device['id'], 'name' : ifname}
        if netifaces.AF_LINK in addrs and addrs[netifaces.AF_LINK][0]['addr'] != '':
            data['mac_address'] = addrs[netifaces.AF_LINK][0]['addr']

        # TODO: get switch info from lldpd        
        if platform.system() == 'Linux':
            phy_int = get_phy_int(ifname)    
            if phy_int == None:
                logging.debug('No physical interface for {}. Ignoring'.format(
                    ifname))
                return None
            elif phy_int != ifname:
                logging.debug('{} is not a physical interface'.format(ifname))
                interface = self.add_vlan_interface(ifname, phy_int, addrs)
                
            else:
                import ethtool
                ff = ethtool.get_formfactor_id(ifname)
                data['form_factor'] = ff
                if ff == 0:
                    data.pop('mac_address')
                interface = self.query_post('dcim/interfaces', data)
                self.prev_ifnames.append(ifname)
        else:
            interface = self.query_post('dcim/interfaces', data)
            self.prev_ifnames.append(ifname)
            phy_int = ifname
                
        
        for k,v in addrs.items():
            if not (k == netifaces.AF_INET or k == netifaces.AF_INET6):
                continue
            for adr in v:
                if phy_int != ifname:
                    if k == netifaces.AF_INET6:
                        ipv6addrs = [i['address'] for i 
                        in self.get_ip_addresses(interface) 
                        if i['family'] == 6]
                        
                        address, netmask = convert_v6_to_simple(adr, ifname)
                        adr_str = '{}/{}'.format(address,netmask)
                        if adr_str in ipv6addrs:
                            continue
                    ipaddr = self.create_ip(adr, k, interface, ifname)
                else:
                    ipaddr = self.create_ip(adr, k, interface)
                if (k in self.gateways and self.gateways[k][1] == ifname):
                    self.update_pri_ip(ipaddr,k)

        return interface

    def get_ip_addresses(self, interface):
        param = {'device_id' : self.device['id'], 'interface_id' : interface['id']}
        return self.query_get('ipam/ip-addresses', param)

    def add_vlan_interface(self, vlan_if, phy_int, addrs):
        logging.debug('Adding vlan {} to {}'.format(vlan_if, phy_int))
        vid = get_vid(vlan_if)

        vlan = self.get_vlan(vid)        
        
        # create parent interface if not exist
        if phy_int not in self.prev_ifnames:
            #phy_interface = self.create_interface(phy_int)
            self.create_interface(phy_int)
            self.prev_ifnames.append(phy_int)
        # else:
        #     param = {'name' : phy_int, 'device_id' : self.device['id']}
        #     phy_interface = self.query_get('dcim/interfaces', param)[0]

        # if phy_interface['mode'] == None or phy_interface['mode']['value'] != 200:
        #     data = {'id' : phy_interface['id'], 'device' : self.device['id'], 
        #     'name' : phy_int, 'mode' : 200, 'tagged_vlans' : [vlan['id']]}
        #     self.query_patch('dcim/interfaces',phy_interface['id'], data)
        # else:
        #     vlans = phy_interface['tagged_vlans']
        #     vids = [i['id'] for i in vlans]
        #     if vlan['id'] not in vids:
        #         vids.append(vlan['id'])
        #         data = {'id' : phy_interface['id'], 'device' : self.device['id'], 
        #         'name' : phy_int, 'mode' : 200, 'tagged_vlans' : vids}
        #         self.query_patch('dcim/interfaces',phy_interface['id'], data)

        data = {'device' : self.device['id'], 'name' : vlan_if, 'untagged_vlan' : vlan['id'], 'type' : 0, 'mode' : 100}
        interface = self.query_post('dcim/interfaces', data)
        self.prev_ifnames.append(vlan_if)

        for k,v in addrs.items():
            if not (k == netifaces.AF_INET or k == netifaces.AF_INET6):
                continue
            for adr in v:
                if k == netifaces.AF_INET6:
                    address, netmask = convert_v6_to_simple(adr, vlan_if)
                    #skip if link addr
                    if address == 'fe80::' : continue
                    ip = netaddr.IPNetwork(address + '/' + netmask)
                elif k == netifaces.AF_INET:
                    ip = netaddr.IPNetwork(adr['addr'] + '/' + adr['netmask'])
                
                self.get_prefix(str(ip.cidr), vlan)                
        return interface

    def get_prefix(self, cidr, vlan):
        param = {'q' : cidr, 'site_id' : self.site['id']} 
        prefix = self.query_get('ipam/prefixes', param)        
        if prefix == None:            
            prefix = self.create_prefix(cidr, vlan)
        elif len(prefix) > 1:
            raise Exception('More than 1 prefix found {}'.format(cidr))
        elif prefix[0]['vlan'] != vlan['id']:
            data = {'vlan' : vlan['id']}
            self.query_patch('ipam/prefixes', prefix[0]['id'], data)
        return prefix

    def create_prefix(self, cidr, vlan):
        logging.debug('Creating Prefix {} vlan {}'.format(cidr, vlan['vid']))
        data = {'prefix' : cidr, 'status' : 1 , 'site' : self.site['id'], 
        'vlan' : vlan['id']}
        return self.query_post('ipam/prefixes', data)

    def get_vlan(self, vid):
        param = {'vid' : vid, 'site_id' : self.site['id']}
        vlan =  self.query_get('ipam/vlans', param)
        if vlan == None:
            vlan = self.create_vlan(vid)
        elif len(vlan) > 1 : 
            raise Exception("There are more than 1 vlan {}".format(vid))
        else:
            vlan = vlan[0]
        return vlan

    def create_vlan(self, vid):
        logging.debug('Creating vlan {}'.format(vid))
        data = {'vid' : vid, 'site' : self.site['id'], 
        'name' : 'vlan{}'.format(vid)}
        vlan = self.query_post('ipam/vlans', data)
        return vlan

    def create_ip(self, addr, addr_family, iface, vlan_ifname = None):
        logging.debug('Creating ip {}'.format(addr['addr']))
        if (addr_family != netifaces.AF_INET and addr_family != netifaces.AF_INET6):
            logging.debug('Ignoring non-IP address {0} for {1} '
            ''.format(addr['addr'], iface['name']))
            return

        logging.debug('Creating IP address {0} for {1} '.format(
            addr['addr'], iface['name']))

        if addr_family == netifaces.AF_INET6:
            if vlan_ifname != None:
                address, netmask = convert_v6_to_simple(addr, vlan_ifname)
            else:
                address, netmask = convert_v6_to_simple(addr, iface['name'])

            if '%' in address:
                address = address[:address.index('%')]
        else:
            address = addr['addr']
            netmask = addr['netmask']

        data = {'address' : '{0}/{1}'.format(address, netmask),
        'interface' : iface['id']}
        ipaddr = self.query_post('ipam/ip-addresses', data)
        return ipaddr        

    def delete_interface(self, iface):
        logging.debug("Deleting " + iface['name'])
        self.query_delete('dcim/interfaces', iface['id'])

    def update_addresses(self, iface, prev_iface):
        logging.debug("Updating interface address :" + iface)
        param = {'device_id' : self.device['id'], 'interface_id' : prev_iface['id']}
        prev_addrs = self.get_addresses(param)
        curr_addrs = netifaces.ifaddresses(iface)
        prev_ips = []
        if prev_addrs != None: 
            prev_ips = [d['address'].split('/')[0] for d in prev_addrs]
        curr_ips = []             
        
        if netifaces.AF_INET in curr_addrs:
            for curr_ipv4 in curr_addrs[netifaces.AF_INET]:
                if curr_ipv4['addr'] not in prev_ips:
                    self.create_ip(curr_ipv4, netifaces.AF_INET, prev_iface)
            curr_ips = [curr_addrs[k][0]['addr'] for k in [netifaces.AF_INET]]

        if netifaces.AF_INET6 in curr_addrs:
            for curr_ipv6 in curr_addrs[netifaces.AF_INET6]:
                curr_ipv6_addr = curr_ipv6['addr'].split('%')[0]
                if curr_ipv6_addr not in prev_ips:
                    self.create_ip(curr_ipv6, netifaces.AF_INET6, prev_iface)
            for ip6 in curr_addrs[netifaces.AF_INET6]:
                curr_ips.append(ip6['addr'].replace('%{}'.format(iface),''))

        if prev_addrs == None:
            return            
        for prev_addr in prev_addrs:
            prev_ip = prev_addr['address'].split('/')[0]
            if len(curr_ips) == 0 or prev_ip not in curr_ips:
                self.delete_ip(prev_addr)

    def delete_ip(self, ip):
        logging.debug("Deleting IP address " + ip['address'])
        self.query_delete('ipam/ip-addresses', ip['id'])
        
    def update_pri_ip(self, ipaddr, addr_family):
        logging.debug("Updating Primary IP: " + ipaddr['address'])

        data = {}
        if addr_family == netifaces.AF_INET:
            data['primary_ip4'] = ipaddr['id']
            #data['primary_ip'] = ipaddr['id']
        elif addr_family == netifaces.AF_INET6:
            data['primary_ip6'] = ipaddr['id']

        self.query_patch('dcim/devices', self.device['id'], data)

    def update_pci(self):
        if platform.system() == 'Windows':
            pass
        elif platform.system() == 'Linux':
            import lshw
            cpus = lshw.get_hw_linux('cpu', self.device['id'])
            nics = lshw.get_hw_linux('network', self.device['id'])            
            #self.update_hw(nics, 'product')
            phy_nics = [d for d in nics if 'product' in d]
            storages = lshw.get_hw_linux('storage', self.device['id'])
            hw = cpus + phy_nics + storages
            self.update_hw(hw)
        elif platform.system() == 'Darwin':
            pass
        else:
            pass

    def update_hw(self, hws):
        prev_hws = self.get_hw()
        if prev_hws != None:
            prev_hws_tags = [d['asset_tag'] for d in prev_hws]
            curr_hws_tags = [d['bus info'] for d in hws if 'bus info' in d]

            for prev_hw in prev_hws:
                if (prev_hw['asset_tag'] not in curr_hws_tags or 
                self.is_hw_changed(prev_hw, hws)):
                    self.delete_hw(prev_hw)

        for hw in hws:            
            if prev_hws == None or hw['bus info'] not in prev_hws_tags:
                self.create_inventory(hw)
    
    def is_hw_changed(self, prev_hw, curr_hws):
        matching_devices = [d for d in curr_hws if d['bus info'] == prev_hw['asset_tag']]
        if len(matching_devices) == 0:
            return True
        elif 'product' in matching_devices[0]:
            return matching_devices[0]['product'][:50] != prev_hw['name']
        else:
            return matching_devices[0]['description'][:50] != prev_hw['name']
 
    def get_hw(self):
        params = {'device_id' : self.device['id']}
        return self.query_get('dcim/inventory-items', params)

    def create_inventory(self, hw):
        logging.debug("Creating HW inventory " + hw['description'])        
        data = {'device' : self.device['id'], 'asset_tag' : hw['bus info'],
        'description' : hw['description']}
        
        if 'product' in hw:
            data['name'] = hw['product']
        else:
            data['name'] = hw['description']       

        self.query_post('dcim/inventory-items',data)

    def delete_hw(self, hw):
        logging.debug('Deleting HW inventory' + hw['name'])
        self.query_delete('dcim/inventory-items', hw['id'])
            

if __name__=='__main__':    
    logging.basicConfig(level=logging.DEBUG)
    agent = NetBoxAgent('netbox_agent.cfg')
    agent.update_interfaces()
    agent.update_pci()
    print('updated')
