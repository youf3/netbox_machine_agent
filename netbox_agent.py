#!/usr/bin/python3
# requirement: dmidecode

import requests, logging, configparser, os, socket, re

import dmidecode

class NetBoxAgent():    
    def __init__(self, configFile):        
        self.load_conf(configFile)
        self.create_header()
        self.get_site()
        if 'rack_group' in self.optional_conf: self.get_rack_group()
        self.get_rack()        
        self.get_device()
        
    
    def create_header(self):        
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': self.token
        }

    def create_conf(self, configFile):
        logging.debug('Creating config file {}'.format(configFile))
        config = configparser.ConfigParser()        
        addr = input('Netbox Server address (e.g. http://localhost:8080) : ')
        config['DEFAULT']['api_base_url'] = '{0}/api'.format(addr)
        config['DEFAULT']['Token'] = input('Authentication Token: ')
        config['DEFAULT']['sitename'] = input('Site name: ')
        config['DEFAULT']['rack_group'] = input('Rack Group: ')
        config['DEFAULT']['rack_name'] = input('Rack Name: ')
        config['DEFAULT']['device_role'] = input('Device Role: ')
        config['DEFAULT']['device_role_color'] = input(
            'Device Role Color Hex (e.g. aa1409): ')

        with open(configFile, 'w') as config_file:
            config.write(config_file)
            logging.debug('Configuration file written : {0}'.format(
                configFile))

    def load_conf(self, configFile):        
        if not os.path.exists(configFile): self.create_conf(configFile)            
        self.config = configparser.ConfigParser()
        self.config.read(configFile)
        self.base_url = self.config['DEFAULT']['api_base_url']
        # self.sitename = config['DEFAULT']['sitename']
        self.token = 'Token {0}'.format(self.config['DEFAULT']['Token'])        
        # self.rack_name = config['DEFAULT']['rack_name']
        # self.device_role_name = config['DEFAULT']['device_role']
        # self.device_role_color = config['DEFAULT']['device_role_color']

        #Load optional configurations
        self.optional_conf_name= ['rack_group']
        self.optional_conf = {}

        for item in self.optional_conf_name:
            try:
                self.optional_conf[item] = self.config['DEFAULT'][item]
            except KeyError:
                logging.debug('{0} not found in configuration'.format(item))   

    def get_site(self):
        sitename = self.config['DEFAULT']['sitename']
        resp = requests.get('{0}/dcim/sites/?name={1}'.format(
            self.base_url, sitename),headers=self.headers).json()
        if len(resp['results']) == 0:
            self.create_site(sitename)
        else: self.site = resp['results'][0]

    def create_site(self, sitename):
        logging.debug('creating site ' + sitename)
        data = {'name' : sitename, 'slug' : sitename}
        resp = requests.post(self.base_url + '/dcim/sites/', json=data,
                            headers=self.headers, allow_redirects=False)
        if resp.status_code != 201: raise Exception(
            'Failed to create site {0}: status {1}: {2}'
            .format(sitename, resp.status_code, resp.reason))
        else : 
            self.site = resp.json()
            logging.debug('Site created {0}({1})'.format(self.site['name'], 
            self.site['id']))     

    def get_rack_group(self):
        rack_group_name = self.optional_conf['rack_group']
        resp = requests.get('{0}/dcim/rack-groups/?site_id={1}&name={2}'.format(
            self.base_url, self.site['id'], self.optional_conf['rack_group']),
            headers=self.headers).json()

        if len(resp['results']) == 0:
            self.create_rack_group(rack_group_name)
        else: self.rack_group = resp['results'][0]

    def create_rack_group(self, rack_group_name):        
        logging.debug('Creating rack group ' + rack_group_name)
        data = {
            'name' : rack_group_name, 'slug' : rack_group_name, 
            'site' : self.site['id']
            }
        resp = requests.post(self.base_url + '/dcim/rack-groups/', json=data,
                            headers=self.headers, allow_redirects=False)
        if resp.status_code != 201: raise Exception(
            'Failed to create rackgroup {0}: status {1}: {2}'
            .format(rack_group_name, resp.status_code, resp.reason))
        else : 
            self.rack_group = resp.json()
            logging.debug('Rack group created {0}({1})'.format(
                self.rack_group['name'], self.rack_group['id']))   

    def get_rack(self):
        rack_name = self.config['DEFAULT']['rack_name']
        url = '{0}/dcim/racks/?name={1}&site_id={2}'.format(self.base_url, 
        rack_name, self.site['id'])
        if 'rack_group' in self.optional_conf:
            url += '&group_id={0}'.format(self.rack_group['id'])
        resp = requests.get(url,headers=self.headers).json()

        if len(resp['results']) == 0:
            self.create_rack(rack_name)
        else: self.rack = resp['results'][0]
        
    # TODO: rack_role and tenent (type and width?)
    def create_rack(self, rack_name):
        logging.debug('Creating rack ' + rack_name)
        data = {
            'name' : rack_name, 'slug' : rack_name, 'site' : self.site['id']
        }

        if 'rack_group' in self.optional_conf:
            data['group'] = self.rack_group['id']

        resp = requests.post(self.base_url + '/dcim/racks/', json=data,
                            headers=self.headers, allow_redirects=False)
        if resp.status_code != 201: raise Exception(
            'Failed to create rack {0}: status {1}: {2}'
            .format(rack_name, resp.status_code, resp.reason))
        else : 
            self.rack = resp.json()
            logging.debug('Rack created {0}({1})'.format(self.rack['name'], 
            self.rack['id']))   

    def get_device_role(self):
        device_role_name = self.config['DEFAULT']['device_role']
        resp = requests.get('{0}/dcim/device-roles/?name={1}&slug={2}'.format(
            self.base_url, device_role_name, device_role_name),
            headers=self.headers).json()
        if len(resp['results']) == 0:
            self.create_device_role(device_role_name)
        else: self.device_role = resp['results'][0]
    
    def create_device_role(self, device_role_name):
        device_role_color = self.config['DEFAULT']['device_role_color']
        logging.debug('Creating device role ' + device_role_name)
        data = {'name' : device_role_name, 'slug' : device_role_name, 
        'color' : device_role_color}

        resp = requests.post(self.base_url + '/dcim/device-roles/', json=data,
                            headers=self.headers, allow_redirects=False)
        if resp.status_code != 201: raise Exception(
            'Failed to create device role {0}: status {1}: {2}'
            .format(device_role_name, resp.status_code, resp.reason))
        else : 
            self.device_role = resp.json()
            logging.debug('Rack created {0}({1})'.format(
                self.device_role['name'], self.device_role['id']))

    def get_manufacturer(self, manufacturer):        
        resp = requests.get('{0}/dcim/manufacturers/?name={1}'.format(
            self.base_url, manufacturer),headers=self.headers).json()

        if len(resp['results']) == 0:
            self.create_manufacturer(manufacturer)
        else: self.manufacturer = resp['results'][0]

    def create_manufacturer(self, manufacturer):
        logging.debug('Creating manufacturer ' + manufacturer)
        data = {'name' : manufacturer, 'slug' : manufacturer}
        resp = requests.post(self.base_url + '/dcim/manufacturers/', 
        json=data, headers=self.headers, allow_redirects=False)

        if resp.status_code != 201: raise Exception(
            'Failed to create manufacturer {0}: status {1}: {2}'
            .format(manufacturer, resp.status_code, resp.reason))
        else : 
            self.manufacturer = resp.json()
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
        
        resp = requests.get('{0}/dcim/device-types/?name={1}'.format(
            self.base_url, model_name),headers=self.headers).json()

        if len(resp['results']) == 0:
            self.create_device_type(model_name,height)
        else: self.device_type = resp['results'][0]
    
    def create_device_type(self, model_name, height):
        logging.debug('Creating device type ' + model_name)
        data = {'manufacturer' : self.manufacturer['id'], 'model' : model_name, 
        'slug' : model_name, 'u_height': height}

        resp = requests.post(self.base_url + '/dcim/device-types/', 
        json=data, headers=self.headers, allow_redirects=False)

        if resp.status_code != 201: raise Exception(
            'Failed to create device type {0}: status {1}: {2}'.format(model_name,
            resp.status_code, resp.reason))
        else : 
            self.device_type = resp.json()
            logging.debug('Manufacturer created {0}({1})'.format(
                self.device_type['model'], self.device_type['id']))

    def get_device(self):
        self.device_name = socket.getfqdn()
        self.get_device_role()
        self.get_device_type()

if __name__=='__main__':    
    logging.basicConfig(level=logging.DEBUG)
    agent = NetBoxAgent('test.cfg')
    print('updated')
    