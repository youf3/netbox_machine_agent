#!/usr/bin/python3
# requirement: dmidecode

import configparser
import logging
import os
import re
import socket
import urllib

import requests

import dmidecode


class NetBoxAgent():    
    def __init__(self, configFile):        
        config, optional_conf = self.load_conf(configFile)
        self.create_header(config['DEFAULT']['Token'])
        self.get_site(config['DEFAULT']['sitename'])

        if 'rack_group' in optional_conf: 
            self.get_rack_group(optional_conf['rack_group'])
        self.get_rack(config['DEFAULT']['rack_name'])        
        self.get_device(self.config['DEFAULT']['device_role'], 
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

        with open(configFile, 'w') as config_file:
            config.write(config_file)
            logging.debug('Configuration file written : {0}'.format(
                configFile))

    def load_conf(self, configFile):        
        if not os.path.exists(configFile): self.create_conf(configFile)            
        self.config = configparser.ConfigParser()
        self.config.read(configFile)
        self.base_url = self.config['DEFAULT']['api_base_url']
        self.token = 'Token {0}'.format(self.config['DEFAULT']['Token'])
        
        optional_conf = self.config['Optional']

        return self.config, optional_conf

    def query_get(self, obj_name, params):
        param_str = urllib.parse.urlencode(params)
        resp = requests.get('{0}/{1}/?{2}'.format(
            self.base_url, obj_name, param_str),headers=self.headers).json()

        if len(resp['results']) == 0 : return None
        else : return resp['results'][0]

    def query_post(self, obj_name, data):
        
        resp = requests.post('{0}/{1}/'.format(self.base_url, obj_name), 
        json=data, headers=self.headers, allow_redirects=False)

        if resp.status_code != 201: raise Exception(
            'Failed to create {0} : {1} status {2}: {3}'
            .format(obj_name, next(iter( data.items())), resp.status_code, 
            resp.reason))
        else : 
            return resp.json()
            

    def get_site(self, sitename):        
        params = {'name' : sitename}

        self.site = self.query_get('dcim/sites',params)
        if self.site == None : self.create_site(sitename)

    def create_site(self, sitename):
        logging.debug('creating site ' + sitename)
        data = {'name' : sitename, 'slug' : sitename}

        self.site = self.query_post('dcim/sites', data)
        print('test')
        
    def get_rack_group(self, rack_group_name):
        params = {'site_id' : self.site['id'], 'name' : rack_group_name}

        self.rack_group = self.query_get('dcim/rack-groups',params)
        if self.rack_group == None: self.create_rack_group(rack_group_name)

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
        
        self.rack = self.query_get('dcim/racks',params)
        if self.rack == None: self.create_rack(rack_name)        
        
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

        self.device_role = self.query_get('dcim/device-roles', params)
        if self.device_role == None: self.create_device_role(device_role_name,
            color)
        
    def create_device_role(self, device_role_name, device_role_color):
        logging.debug('Creating device role ' + device_role_name)
        data = {'name' : device_role_name, 'slug' : device_role_name, 
        'color' : device_role_color}

        self.device_role = self.query_post('dcim/device-roles', data)
        logging.debug('Device role created {0}({1})'.format(self.device_role['name'], 
        self.device_role['id']))

    def get_manufacturer(self, manufacturer):
        param = {'name' : manufacturer}

        self.manufacturer = self.query_get('dcim/manufacturers', param)
        if self.manufacturer == None : self.create_manufacturer(manufacturer)

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
                manufacturer = re.sub(r'[^-a-zA-Z0-9_]','_',
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
        
        param = {'name' : model_name}
        self.device_type = self.query_get('dcim/device-types', param)
        if self.device_type == None: self.create_device_type(model_name,height)        
    
    def create_device_type(self, model_name, height):
        logging.debug('Creating device type ' + model_name)
        data = {'manufacturer' : self.manufacturer['id'], 'model' : model_name, 
        'slug' : model_name, 'u_height': height}

        self.device_type = self.query_post('dcim/device-types', data)
        logging.debug('Device  created {0}({1})'.format(
            self.device_type['model'], self.device_type['id']))

    def get_device(self, role, role_color):
        device_name = socket.getfqdn()
        self.get_device_role(role, role_color)
        self.get_device_type()

        param = {'name' : device_name, 'manufacturer_id' : self.manufacturer['id'],
        'role_id' : self.device_role['id'], 'site_id' : self.site['id'], 
        'rack_group_id' : self.rack_group['id'], 'rack_id' : self.rack['id']}

        self.device = self.query_get('dcim/devices', param)
        if self.device == None: self.create_device(device_name)

    def create_device(self, device_name):
        logging.debug('Creating device ' + device_name)

        data = {'name' : device_name, 'device_type' : self.device_type['id'],
        'device_role' : self.device_role['id'], 'site' : self.site['id'], 
        'rack' : self.rack['id']}

        self.device = self.query_post('dcim/devices',data)

    def get_interfaces(self):
        param = {'device_id' : self.device['id']}

        return self.query_get('dcim/interfaces', param)

    def update_interfaces(self):
        interfaces = self.get_interfaces()
        


if __name__=='__main__':    
    logging.basicConfig(level=logging.DEBUG)
    agent = NetBoxAgent('test.cfg')
    agent.update_interfaces()
    print('updated')
