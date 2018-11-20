#!/usr/bin/python3

import requests, logging, configparser, os, socket

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
        config = configparser.ConfigParser()
        config.read(configFile)
        self.base_url = config['DEFAULT']['api_base_url']
        self.sitename = config['DEFAULT']['sitename']
        self.token = 'Token {0}'.format(config['DEFAULT']['Token'])        
        self.rack_name = config['DEFAULT']['rack_name']
        self.device_role_name = config['DEFAULT']['device_role']
        self.device_role_color = config['DEFAULT']['device_role_color']

        #Load optional configurations
        self.optional_conf_name= ['rack_group']
        self.optional_conf = {}

        for item in self.optional_conf_name:
            try:
                self.optional_conf[item] = config['DEFAULT'][item]
            except KeyError:
                logging.debug('{0} not found in configuration'.format(item))   

    def get_site(self):  
        resp = requests.get('{0}/dcim/sites/?name={1}'.format(
            self.base_url, self.sitename),headers=self.headers).json()
        if len(resp['results']) == 0:
            self.create_site()
        else: self.site = resp['results'][0]

    def create_site(self):
        logging.debug('creating site ' + self.sitename)
        data = {'name' : self.sitename, 'slug' : self.sitename}
        resp = requests.post(self.base_url + '/dcim/sites/', json=data,
                            headers=self.headers, allow_redirects=False)
        if resp.status_code != 201: raise Exception(
            'Failed to create site {0}: status {1}: {2}'
            .format(self.sitename, resp.status_code, resp.reason))
        else : 
            self.site = resp.json()
            logging.debug('Site created {0}({1})'.format(self.sitename, 
            self.site['id']))     

    def get_rack_group(self):
        resp = requests.get('{0}/dcim/rack-groups/?site_id={1}&name={2}'.format(
            self.base_url, self.site['id'], self.optional_conf['rack_group']),
            headers=self.headers).json()

        if len(resp['results']) == 0:
            self.create_rack_group()
        else: self.rack_group = resp['results'][0]

    def create_rack_group(self):
        rack_group_name = self.optional_conf['rack_group']
        logging.debug('Creating rack group ' + rack_group_name)
        data = {
            'name' : rack_group_name, 'slug' : rack_group_name, 'site' : self.site['id']
            }
        resp = requests.post(self.base_url + '/dcim/rack-groups/', json=data,
                            headers=self.headers, allow_redirects=False)
        if resp.status_code != 201: raise Exception(
            'Failed to create rackgroup {0}: status {1}: {2}'
            .format(rack_group_name, resp.status_code, resp.reason))
        else : 
            self.rack_group = resp.json()
            logging.debug('Rack group created {0}({1})'.format(self.rack_group['name'], 
            self.rack_group['id']))   

    def get_rack(self):
        url = '{0}/dcim/racks/?name={1}&site_id={2}'.format(self.base_url, self.rack_name, 
        self.site['id'])
        if 'rack_group' in self.optional_conf:
            url += '&group_id={0}'.format(self.rack_group['id'])
        resp = requests.get(url,headers=self.headers).json()

        if len(resp['results']) == 0:
            self.create_rack()
        else: self.rack = resp['results'][0]
        
    # TODO: rack_role and tenent (type and width?)
    def create_rack(self):
        logging.debug('Creating rack ' + self.rack_name)
        data = {
            'name' : self.rack_name, 'slug' : self.rack_name, 'site' : self.site['id']
        }

        if 'rack_group' in self.optional_conf:
            data['group'] = self.rack_group['id']

        resp = requests.post(self.base_url + '/dcim/racks/', json=data,
                            headers=self.headers, allow_redirects=False)
        if resp.status_code != 201: raise Exception(
            'Failed to create rack {0}: status {1}: {2}'
            .format(self.rack_name, resp.status_code, resp.reason))
        else : 
            self.rack = resp.json()
            logging.debug('Rack created {0}({1})'.format(self.rack['name'], self.rack['id']))   

    def get_device(self):
        self.device_name = socket.getfqdn()
        self.get_device_role()

    def get_device_role(self):        
        resp = requests.get('{0}/dcim/device-roles/?name={1}&slug={2}'.format(self.base_url, 
        self.device_role_name, self.device_role_name),headers=self.headers).json()
        if len(resp['results']) == 0:
            self.create_device_role()
        else: self.device_role = resp['results'][0]
    
    def create_device_role(self):
        logging.debug('Creating device role ' + self.device_role_name)
        data = {'name' : self.device_role_name, 'slug' : self.device_role_name, 
        'color' : self.device_role_color}

        resp = requests.post(self.base_url + '/dcim/device-roles/', json=data,
                            headers=self.headers, allow_redirects=False)
        if resp.status_code != 201: raise Exception(
            'Failed to create device role {0}: status {1}: {2}'
            .format(self.device_role_name, resp.status_code, resp.reason))
        else : 
            self.device_role = resp.json()
            logging.debug('Rack created {0}({1})'.format(self.device_role['name'], 
            self.device_role['id']))

if __name__=='__main__':    
    logging.basicConfig(level=logging.DEBUG)
    agent = NetBoxAgent('test.cfg')
    print('updated')
    