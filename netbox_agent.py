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
        #config['DEFAULT']['rack_group'] = input('Rack Group: ')
        config['DEFAULT']['rack_name'] = input('Rack Name: ')
        config['DEFAULT']['device_role'] = input('Device Role: ')

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
        self.device_role = config['DEFAULT']['device_role']

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
        logging.debug('creating site' + self.sitename)
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
        logging.debug('Creating rack group' + rack_group_name)
        data = {
            'name' : rack_group_name, 'slug' : rack_group_name, 
            'site' : {
                'id' : self.site['id'], 'name' : self.site['name'], 
                'slug' : self.site['slug']
                }
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
        # resp = requests.get('{0}/dcim/racks/?site_id={1}&name={2}'.format(
        #     self.base_url, self.site['id'], self.optional_conf['rack_group']),
        #     headers=self.headers).json()

        # if len(resp['results']) == 0:
        #     self.create_rack_group()
        # else: self.rack_group = resp['results'][0]
        pass
        
    def get_device(self):
        self.device_name = socket.getfqdn()

if __name__=='__main__':    
    logging.basicConfig(level=logging.DEBUG)
    agent = NetBoxAgent('test.cfg')
    print('updated')
    