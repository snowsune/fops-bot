#!/usr/bin/env python
# Scrapes pfSense DHCP Leases into List of (IP, MAC, Hostname) format. 
# Change URL/Username/Password below ... pip install lxml ... then you are all set.
#
# Modified 6/23/2019 (FryGuy)
# Edits: Aligned IP/MAC/Hostname into struct accounting for blank lines
# Minor: Cleaned up spacing, created global url/user/password vars, removed write to file
# Original Code/Inspiration: https://gist.github.com/pletch/037a4a01c95688fff65752379534455f

# modified 9/6/2023 (clayrosenthal)
# edits: using iter methods rather than just xpath to find leases
# also now gets all columns rather than just ip, mac, hostname
# minor: added env vars for url, user, password
# Original Code/Inspiration: https://gist.github.com/fryguy04/7d12b789260c47c571f42e5bc733a813

import json
import os
import re

import requests
import urllib3
from lxml import html

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# set env vars to match your pfsense setup
url = os.environ.get('PFSENSE_URL', '') 
url = url.rstrip('/') + '/status_dhcp_leases.php' 
user = os.environ.get('PFSENSE_USER', '')
password = os.environ.get('PFSENSE_PASSWORD', '') 


def scrape_pfsense_dhcp(url, user, password):
    s = requests.session()
    r = s.get(url, verify=False)

    matchme = 'csrfMagicToken = "(.*)";var'

    csrf = re.search(matchme, str(r.text))

    payload = {
        '__csrf_magic' : csrf.group(1),
        'login' : 'Login',
        'usernamefld' : user,
        'passwordfld' : password
    }

    r = s.post(url, data=payload, verify=False)
    r = s.get(url, verify=False)
    tree = html.fromstring(r.content)

    lease_table = tree.get_element_by_id('leaselist')
    table_header = next(sib for sib in lease_table.itersiblings(preceding=True) if sib.tag == 'thead')
    table_headers = [head.text for head in next(table_header.iterchildren()).iterchildren()]

    dhcp_list = []
    for lease in lease_table.iterchildren(tag='tr'):
        lease_dict = {}
        for i, element in enumerate(lease.iterchildren(tag='td')):
            if i == 0:
                continue
            lease_dict[table_headers[i]] = element.text.strip() if element.text is not None else ''
        dhcp_list.append(lease_dict)

    return dhcp_list


if __name__ == "__main__":
    dhcp_list = scrape_pfsense_dhcp(url, user, password)

    print(json.dumps(dhcp_list, indent=4))
