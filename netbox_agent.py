#!/usr/bin/python3

import requests
  
apiBaseUrl = "http://netmon:32775/api"
sitename = 'icair'

headers = {  
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'Authorization': '0123456789abcdef0123456789abcdef01234567'
}

def get_site(sitename):  
    resp = requests.get(apiBaseUrl + '/dcim/sites?q=' + sitename,
                        headers=headers).json()
    return resp['results']

def set_site(sitename):
    data = {'name' : sitename, 'slug' : sitename}
    resp = requests.post(apiBaseUrl + '/dcim/sites', json=data,
                        headers=headers, allow_redirects=False)
    if resp.status_code != 201:
        raise ApiError('POST /tasks/ {}'.format(resp.status_code))
    return resp['results']
    print('h')

if __name__=='__main__':

    if len(get_site(sitename)) == 0:
        set_site(sitename)
      