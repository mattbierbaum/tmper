from __future__ import print_function

import re
import os
import sys
import json
import webbrowser
import requests

try:
    import urlparse
    from urllib import urlencode
except:
    # Python3 imports
    import urllib.parse as urlparse
    from urllib.parse import urlencode

import pkg_resources
__version__ = pkg_resources.require("tmpr")[0].version

#=============================================================================
# command line utility features
#=============================================================================
def conf_file():
    return os.path.expanduser('~/.tmpr.json')

def argformat(d):
    out = {k:v for k,v in d.items() if v}
    return '?'+urlencode(out) if out else ''

def conf_read(key):
    filename = conf_file()
    if os.path.exists(filename):
        return json.load(open(filename)).get(key)
    return {}

def conf(url='', password=''):
    filename = conf_file()
    if os.path.exists(filename):
        cf = json.load(open(filename))
    else:
        cf = {}

    if url:
        cf.update({'url': url})
    if password:
        cf.update({'pass': password})
    json.dump(cf, open(filename, 'w'))

def download(url, code, password='', browser=False):
    """ Download a file 'code' from the tmpr 'url' """
    url = url or conf_read('url')
    password = password or conf_read('pass')

    if not url:
        print("No URL provided! Provide one or set on via conf.")
        sys.exit(1)

    if browser:
        arg = argformat({'key': password, 'v': 1})
        rqt = '{}{}'.format(urlparse.urljoin(url, code), arg)
        webbrowser.open(rqt, new=True)
        return

    arg = argformat({'key': password})
    rqt = '{}{}'.format(urlparse.urljoin(url, code), arg)
    hdr = {'User-Agent': 'tmpr/{}'.format(__version__)}
    response = requests.get(rqt, headers=hdr)

    # if we get an error, print the error and stop
    if response.status_code != 200:
        print(
            "Code '{}' not found at '{}', '{}'".format(
                code, url, response.content.decode('utf-8')
            ), file=sys.stderr
        )
        sys.exit(1)

    headers = response.headers
    contents = response.content
    response.close()

    # extract the intended filename from the headers
    filename = re.match(
        '.*filename="(.*)"$', headers['Content-Disposition']
    ).groups()[0]

    # make sure we are not overwriting any files by appending numbers to the end
    if os.path.exists(filename):
        for i in range(1000):
            newname = '{}-{}'.format(filename, i)
            if not os.path.exists(newname):
                filename = newname
                break

    with open(filename, 'wb') as f:
        f.write(contents)

    print(filename)

def upload(url, filename, code='', password='', num=1, time=''):
    """ Upload the file 'filename' to tmpr url """
    url = url or conf_read('url')
    password = password or conf_read('pass')

    if not url:
        print("No URL provided! Provide one or set on via conf.", file=sys.stderr)
        sys.exit(1)

    url = url if not code else urlparse.urljoin(url, code)
    arg = {} if not password else {'key': password}
    arg = arg if num == 1 else dict(arg, n=num)
    arg = arg if time == '' else dict(arg, time=time)

    name = os.path.basename(filename)

    if not os.path.exists(filename):
        print("File '{}' does not exist".format(filename), file=sys.stderr)
        sys.exit(1)

    with open(filename) as f:
        hdr = {'User-Agent': 'tmpr/{}'.format(__version__)}
        r = requests.post(url, data=arg, files={name: f.read()}, headers=hdr)
        print(r.content.decode('utf-8'))

