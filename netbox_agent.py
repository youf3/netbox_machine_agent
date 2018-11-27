#!/usr/bin/python3
# requirement: dmidecode

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

class NetBoxAgent():    
    def __init__(self, configFile):        
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

        self.get_device(config['DEFAULT']['device_role'], 
        config['DEFAULT']['device_role_color'])
        
    
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
        config['Optional']['rack_group'] = input('Rack Group: ')
        config['DEFAULT']['rack_name'] = input('Rack Name: ')
        config['DEFAULT']['device_role'] = input('Device Role: ')
        config['DEFAULT']['device_role_color'] = input(
            'Device Role Color Hex (e.g. aa1409): ')
        config['Optional']['position'] = input(
            'Mounted rack position (lowest) : ')
        config['Optional']['face'] = input(
            'Mounted rack face (0 for front, 1 for back) : ')

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
        elif len(resp['results']) == 0 : return None
        else : return resp['results']

    def query_post(self, obj_name, data):        
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
            'name' : rack_name, 'slug' : rack_name, 'site' : self.site['id']
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
        logging.debug('Device role created {0}({1})'.format(self.device_role['name'], 
        self.device_role['id']))

    def get_manufacturer(self, manufacturer):
        param = {'name' : manufacturer}

        manufacturers = self.query_get('dcim/manufacturers', param)
        if manufacturers == None : self.create_manufacturer(manufacturer)
        else : self.manufacturer = manufacturers[0]

    def create_manufacturer(self, manufacturer):
        logging.debug('Creating manufacturer ' + manufacturer)
        data = {'name' : manufacturer, 'slug' : manufacturer}
        
        self.manufacturer = self.query_post('dcim/manufacturers', data)
        logging.debug('Manufacturer created {0}({1})'.format(
            self.manufacturer['name'], self.manufacturer['id']))

    def get_device_type(self):
        sysinfo = dmidecode.profile()

        for item in sysinfo:
            if 'system' in item[0] and ('Manufacturer' in item[1] and 
            'Product Name' in item[1]):                
                manufacturer = re.sub(r'([^-a-zA-Z0-9_])+','_',
                item[1]['Manufacturer'])
                model_name = re.sub(r'[^-a-zA-Z0-9_]','_',
                item[1]['Product Name'])
                if manufacturer.endswith('_') : manufacturer = manufacturer[:-1]                
                if model_name.endswith('_') : model_name = model_name[:-1]
                logging.debug('System information found {0} {1}'.format(
                    manufacturer, model_name))
                
            if 'chassis' in item[0]:                
                height = item[1]['Height']
                if height == 'Unspecified': height = 1
                else : height = int(height.split(' ')[0])
                logging.debug('Chassis information found. Height {0}'.format(
                    height))

        self.get_manufacturer(manufacturer)
        
        param = {'model' : model_name}
        device_type = self.query_get('dcim/device-types', param)
        if device_type == None: self.create_device_type(model_name,height)
        else : self.device_type = device_type[0]
    
    def create_device_type(self, model_name, height):
        logging.debug('Creating device type ' + model_name)
        data = {'manufacturer' : self.manufacturer['id'], 'model' : model_name, 
        'slug' : model_name, 'u_height': height}

        self.device_type = self.query_post('dcim/device-types', data)
        logging.debug('Device  created {0}({1})'.format(
            self.device_type['model'], self.device_type['id']))

    def get_device(self, role, role_color):
        device_name = socket.gethostname()
        self.get_device_role(role, role_color)
        self.get_device_type()

        param = {'name' : device_name, 'manufacturer_id' : self.manufacturer['id']}

        device = self.query_get('dcim/devices', param)
        if device == None : self.create_device(device_name)
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
        data = {'name' : prev_device['name'], 'manufacturer_id' : self.manufacturer['id'],
        'role_id' : self.device_role['id'], 'site_id' : self.site['id'], 
        'rack_group_id' : self.rack_group['id'], 'rack_id' : self.rack['id']}

        if self.rack_position != None:
            data['position'] = self.rack_position
            data['face'] = self.rack_face
        return self.query_patch('dcim/devices', prev_device['id'],data)

    def get_interfaces(self):
        param = {'device_id' : self.device['id']}

        return self.query_get('dcim/interfaces', param)

    def get_addresses(self, param):        
        return self.query_get('ipam/ip-addresses', param)

    def update_interfaces(self):
        logging.debug("Updating network interfaces")
        prev_ifaces = self.get_interfaces()        
        curr_ifaces = netifaces.interfaces()
        gateways =  netifaces.gateways()

        # Delete interfaces not exist
        if prev_ifaces != None:
            prev_ifnames = [d['name'] for d in prev_ifaces]
            for prev_if in prev_ifaces:
                if prev_if['name'] not in curr_ifaces:                    
                    self.delete_interface(prev_if)

        for iface in curr_ifaces:            
            if prev_ifaces is None or iface not in prev_ifnames:
                self.create_interface(iface, gateways['default'])
            elif iface in prev_ifnames:
                prev_iface = [d for d in prev_ifaces if d['name'] == iface][0]
                self.update_addresses(iface, prev_iface)

    def create_interface(self, ifname, gws):
        logging.debug('Creating interface ' + ifname)
        addrs = netifaces.ifaddresses(ifname)
        
        data = {'device' : self.device['id'], 'name' : ifname}
        if netifaces.AF_LINK in addrs:
            data['mac_address'] = addrs[netifaces.AF_LINK][0]['addr']

        # TODO: get switch info from lldpd
        if platform.system() == 'Windows':
            pass
        elif platform.system() == 'Linux':
            import ethtool
            ff = ethtool.get_formfactor_id(ifname)
            data['form_factor'] = ff
        else:
            pass

        interface = self.query_post('dcim/interfaces', data)
        for k,v in addrs.items():            
            for adr in v:                
                ipaddr = self.create_ip(adr, k, interface)
                if (k in gws and gws[k][1] == ifname):
                    self.update_pri_ip(ipaddr,k)

    def create_ip(self, addr, addr_family, iface):
        if (addr_family != netifaces.AF_INET and addr_family != netifaces.AF_INET6):
            logging.debug('Ignoring non-IP address {0} for {1} '
            ''.format(addr['addr'], iface['name']))
            return

        logging.debug('Creating IP address {0} for {1} '.format(
            addr['addr'], iface['name']))

        if addr_family == netifaces.AF_INET6:
            address = addr['addr'].replace('%{}'.format(iface['name']), '')
            netmask = addr['netmask'].split('/')[-1]
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
            nics = lshw.get_hw_linux('network', self.device['id'])            
            #self.update_hw(nics, 'product')
            phy_nics = [d for d in nics if 'product' in d]
            storages = lshw.get_hw_linux('storage', self.device['id'])
            hw = phy_nics + storages
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
                if prev_hw['asset_tag'] not in curr_hws_tags or self.is_hw_changed(prev_hw, hws):
                    self.delete_hw(prev_hw)

        for hw in hws:            
            if prev_hws == None or hw['bus info'] not in prev_hws_tags:
                self.create_inventory(hw)
    
    def is_hw_changed(self, prev_hw, curr_hws):
        matching_devices = [d for d in curr_hws if d['bus info'] == prev_hw['asset_tag']]
        if len(matching_devices) == 0:
            return True
        elif matching_devices[0]['description'] != prev_hw['description']:
            return True
        else: return False

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
    agent = NetBoxAgent('test.cfg')
    agent.update_interfaces()
    agent.update_pci()
    print('updated')
